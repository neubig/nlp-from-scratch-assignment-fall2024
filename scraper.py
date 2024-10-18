from typing import List, Optional, Tuple, Iterator, Dict, Any
from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter
from dotenv import load_dotenv
#from pypdf import PdfReader, PageObject
import pdfplumber
import requests
from requests.exceptions import *
import traceback
import argparse
import sys
import re
import os
import io

from chunking import *

load_dotenv()

default_prompt = "You are a quiz generation tool. When given a document, you will generate at most 10 question and answer pairs formatted as below. " + \
    "The question should be about a verifiable fact, such as the name of a person, place, or event, a date of a historical or scheduled event, etc. " + \
    "Answers should be concise, consisting of a few words at most. Do not generate questions which do not have a clear answer in the documents you have seen. " + \
    "Do not generate questions about the document itself, such as \"When was the list of the 100 most populous cities of the United States last updated?\". " + \
    "If you are unable to generate any suitable questions from the document, output `[NO DATA]` and quit. " + \
    "If a question has more than one possible answer, separate correct answers with a semicolon (`;`)." + \
'''
Here is the desired format:

Q: Who is Pittsburgh named after?
A: William Pitt

Q: What famous machine learning venue had its first conference in Pittsburgh in 1980?
A: ICML

Q: What musical artist is performing at PPG Arena on October 13?
A: Billie Eilish

Q: What major league sports teams are based in Pittsburgh?
A: Steelers;Penguins;Pirates'''

def get(url : str) -> Tuple[str,str]:
    try:
        res = requests.get(url)
        content_type = res.headers['Content-Type'].split(';')[0]
        return res.text, content_type, res.content
    except SSLError:
        print("SSL certificate verification failed. Retrying without verification...")
        res = requests.get(url,verify=False)
        content_type = res.headers['Content-Type'].split(';')[0]
        return res.text, content_type, res.content

def wiki_cleaner(soup : BeautifulSoup):
    """
    Specialized parser for cleaning up wikipedia articles
    """
    ...

def soup_chunker(body : BeautifulSoup,chunkSize=DEFAULT_CHUNKSIZE) -> Iterator[str]:
    """
    Utility for chunking the main body of a webpage into sizeable chunks
    """
    def to_truncated_md(soup):
        out = None
        if soup is None:
            return ''
        if 'NavigableString' in str(type(soup)):
            out = str(soup)
        elif 'Comment' in str(type(soup)):
            out = ''
        elif 'Doctype' in str(type(soup)):
            out = ''
        else:
            out = MarkdownConverter().convert_soup(soup) #soupcan.get_text()
        # Get rid of comically long strings of consecutive newlines
        while '\n\n\n' in out:
            out = out.replace('\n\n\n','\n\n')
        return out

    return SoupCan(body,stringify=to_truncated_md,max_tokens=chunkSize)

def parse_raw(raw_data, content_type='text/html', chunk=False,**kwargs) -> Optional[Iterator[str] | str]:
    match content_type:
        case 'text/html':
            soup = BeautifulSoup(raw_data,'html.parser')
            # TODO remove irrelevant images
            for img in soup.find_all('img'):
                img : BeautifulSoup = img
                repl = BeautifulSoup(f'<p>(image) {img.attrs.get("alt") or ""}</p>','html.parser').p
                img.replace_with(repl)
            body_candidates = soup.find_all(class_=re.compile(r'((b|B)ody-?(c|C)ontent|(c|C)ontent-?(a|A)rea)')) # TODO identify possible ID/class tags
            body = body_candidates[0] if len(body_candidates) > 0 else soup.body
            if chunk:
                return soup_chunker(body,**kwargs)
            else:
                parsed_text = MarkdownConverter().convert_soup(body)
                # Get rid of comically long strings of consecutive newlines
                while '\n\n\n' in parsed_text:
                    parsed_text = parsed_text.replace('\n\n\n','\n\n')
                return parsed_text
        
        case 'application/pdf':
            with pdfplumber.open(io.BytesIO(raw_data)) as pdf:
                pages = [page.extract_text(layout=True) for page in pdf.pages]
                #objects : Dict[Any,Any] = reader.resolved_objects or {}
                #print([x['text'] for x in pdf.pages[0].extract_text_lines()])
                if chunk:
                    return iter(PDFLines(pages,max_tokens=kwargs['chunkSize']))
                else:
                    return '\n'.join(pages)

        case _:
            print('Unsupported content type:',content_type)
    pass

def generate_questions(document : str, prompt : Optional[str] = None):
    """
    Generates questions from a given document.

    Inputs:
        document : str, a markdown or plaintext document to search over
    """
    if prompt is None:
        prompt = default_prompt
    # TODO migrate to personal gradio space
    # from gradio_client import Client
    from huggingface_hub import InferenceClient

    messages = [
        {"role": "system", "content": prompt},
        # TODO maybe format 
        {"role": "user", "content": re.sub(r'!\[\]\(.*\.(png|svg|jpg|gif|webp|PNG|SVG|JPG|GIF|WEBP)\)','',document)},
    ]
    client = InferenceClient(api_key=os.getenv('HF_API_KEY'))

    out = []
    for message in client.chat_completion(
	    model="meta-llama/Llama-3.2-11B-Vision-Instruct",
	    messages=messages,
	    max_tokens=500,
	    stream=True,
    ):
        out.append(message.choices[0].delta.content)
    print('Line finished',file=sys.stderr)
    return ''.join(out)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='https://en.wikipedia.org/')
    parser.add_argument('--chunk-size', default=DEFAULT_CHUNKSIZE, type=int)
    parser.add_argument('-Q','--get-questions', action='store_true')
    parser.add_argument('-L','--get-links', action='store_true')
    parser.add_argument('-p','--promptfile')
    args = parser.parse_args()
    data = None
    text, content_type, binary = get(args.url)
    if 'text' in content_type:
        data = text
        with open(f'working/raw.{content_type.split("/")[-1]}','w') as f:
            f.write(text)
    else:
        data = binary
        with open(f'working/raw.{content_type.split("/")[-1]}','wb') as f:
            f.write(binary)


    if args.get_questions:
        # Crucially, we will need to chunk the data
        document = parse_raw(data,content_type,chunk=True,chunkSize=args.chunk_size)
        prompt = None
        if args.promptfile is not None:
            with open(args.promptfile,'r') as inf:
                prompt = inf.read()
            print('Using custom prompt:')
            print(prompt,'\n')
        try:
            for subsection in document:
                with open('working/etc.out','a') as errf:
                    print(subsection,file=errf)
                    print('|'+('-'*100)+'|',file=errf)
                with open('working/qs.txt','a') as outf:
                    print(generate_questions(subsection,prompt),file=outf)
            with open('working/qs.txt','a') as outf:
                print("[EOF]",file=outf)
        except KeyboardInterrupt:
            with open('working/qs.txt','a') as outf:
                print("[INTERRUPT]",file=outf)
            print('Execution interrupted!',file=sys.stderr)
        except Exception:
            with open('working/qs.txt','a') as outf:
                print("[INTERRUPT]",file=outf)
            print('Execution interrupted!',file=sys.stderr)
            traceback.print_exc()

    with open('working/out.txt','w') as f:
        f.write(parse_raw(data,content_type))
    
    if args.get_links and content_type == 'text/html':
        soup = BeautifulSoup(data,'html.parser')
        links = soup.find_all('a')
        with open('working/links.md','a') as f:
            print('##',args.url,file=f)
            for link in links:
                href = link.attrs.get('href')
                # Ignore empty and section links
                if href is None:
                    continue
                if href.startswith('#') or href.startswith('?'):
                    continue
                # Force link to be absolute, not relative
                if href.startswith('//'):
                    href = args.url.split('//')[0] + href
                elif not href.startswith('http'):
                    href = os.path.join(args.url,href)
                link.attrs['href'] = href
                print('-',MarkdownConverter().convert(link.prettify()),file=f)
            print('-'*100,end='\n\n',file=f)
    
    print('Execution complete!',file=sys.stderr)
    