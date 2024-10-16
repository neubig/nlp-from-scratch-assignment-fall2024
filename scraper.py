from typing import List, Optional, Tuple, Iterator
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from dotenv import load_dotenv
import requests
from requests.exceptions import *
import argparse
import sys
import re
import os

from chunking import *

load_dotenv()

prompt_context = "You are a quiz generation tool. When given a document, you will generate at most 10 question and answer pairs formatted as below. " + \
    "The question should be about a verifiable fact, such as the name of a person, place, or event, a date of a historical or scheduled event, etc. " + \
    "Answers should be concise, consisting of a few words at most. Do not generate questions which do not have a clear answer in the documents you have seen. " + \
    "Do not generate questions about the document itself, such as \"When was the list of the 100 most populous cities of the United States last updated?\". " + \
    "If you are unable to generate any suitable questions from the document, output `[NO DATA]` and quit." + \
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
        return res.text, content_type
    except SSLError:
        print("SSL certificate verification failed. Retrying without verification...")
        res = requests.get(url,verify=False)
        content_type = res.headers['Content-Type'].split(';')[0]
        return res.text, content_type

def wiki_cleaner(soup : BeautifulSoup):
    """
    Specialized parser for cleaning up wikipedia articles
    """
    ...

def soup_chunker(body : BeautifulSoup,chunkSize=8192) -> Iterator[str]:
    """
    Utility for chunking the main body of a webpage into sizeable chunks
    """
    def to_truncated_md(soup):
        out = None
        if 'NavigableString' in str(type(soup)):
            out = str(soup)
        elif 'Comment' in str(type(soup)):
            out = ''
        else:
            out = md(soup.prettify()) #soupcan.get_text()
        # Get rid of comically long strings of consecutive newlines
        while '\n\n\n' in out:
            out = out.replace('\n\n\n','\n\n')
        return out

    return SoupCan(body,stringify=to_truncated_md,max_tokens=chunkSize)

def parse_raw(raw_text, content_type='text/html', chunk=False,**kwargs) -> Optional[Iterator[str] | str]:
    match content_type:
        case 'text/html':
            soup = BeautifulSoup(raw_text,'html.parser')
            # TODO remove irrelevant images
            # for img in soupcan.find_all('img'):
            body_candidates = soup.find_all(class_=re.compile(r'((b|B)ody-?(c|C)ontent|(c|C)ontent-?(a|A)rea)')) # TODO identify possible ID/class tags
            body = body_candidates[0] if len(body_candidates) > 0 else soup.body
            if chunk:
                return soup_chunker(body,**kwargs)
            else:
                parsed_text = md(body.prettify())
                # Get rid of comically long strings of consecutive newlines
                while '\n\n\n' in parsed_text:
                    parsed_text = parsed_text.replace('\n\n\n','\n\n')
                return parsed_text

        case _:
            print('Unsupported content type:',content_type)
    pass

def generate_questions(document : str):
    """
    Generates questions from a given document.

    Inputs:
        document : str, a markdown or plaintext document to search over
    """
    # TODO migrate to personal gradio space
    # from gradio_client import Client
    from huggingface_hub import InferenceClient

    messages = [
        {"role": "system", "content": prompt_context},
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
    parser.add_argument('--chunk-size', default=8192, type=int)
    parser.add_argument('-Q','--get-questions', action='store_true')
    args = parser.parse_args()
    text, content_type = get(args.url)
    with open(f'raw.{content_type.split("/")[-1]}','w') as f:
        f.write(text)

    if args.get_questions:
        # Crucially, we will need to chunk the data
        document = parse_raw(text,content_type,chunk=True,chunkSize=args.chunk_size)
        for subsection in document:
            with open('etc.out','a') as errf:
                print(subsection,file=errf)
                print('--------',file=errf)
            with open('qs.txt','a') as outf:
                print(generate_questions(subsection),file=outf)

    with open('out.txt','w') as f:
        f.write(parse_raw(text,content_type))
    
    print('Execution complete!',file=sys.stderr)
    