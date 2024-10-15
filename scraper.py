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

def soup_chunker(body : BeautifulSoup) -> Iterator[str]:
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

    return SoupCan(body,stringify=to_truncated_md)

def parse_raw(raw_text, content_type='text/html', chunk=False) -> Optional[Iterator[str] | str]:
    match content_type:
        case 'text/html':
            soup = BeautifulSoup(raw_text,'html.parser')
            # TODO remove irrelevant images
            # for img in soupcan.find_all('img'):
            body_candidates = soup.find_all(class_=re.compile(r'((b|B)ody-?(c|C)ontent|(c|C)ontent-?(a|A)rea)')) # TODO identify possible ID/class tags
            body = body_candidates[0] if len(body_candidates) > 0 else soup.body
            if chunk:
                return soup_chunker(body)
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
        {"role": "system", "content": '''You are a quiz generation tool. When given a document, you will generate 10 question and answer pairs formatted as below:

Q: Who is Pittsburgh named after?
A: William Pitt

Q: What famous machine learning venue had its first conference in Pittsburgh in 1980?
A: ICML

Q: What musical artist is performing at PPG Arena on October 13?
A: Billie Eilish'''},
        # TODO maybe format 
        {"role": "user", "content": re.sub(r'!\[\]\(.*\.(png|svg|jpg|gif|webp|PNG|SVG|JPG|GIF|WEBP)\)','',document)},
    ]
    client = InferenceClient(api_key=os.getenv('HF_API_KEY'))

    for message in client.chat_completion(
	    model="meta-llama/Llama-3.2-11B-Vision-Instruct",
	    messages=messages,
	    max_tokens=500,
	    stream=True,
    ):
        print(message.choices[0].delta.content, end="")
    ...

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='https://en.wikipedia.org/')
    parser.add_argument('-Q','--get-questions', action='store_true')
    args = parser.parse_args()
    text, content_type = get(args.url)
    with open(f'raw.{content_type.split("/")[-1]}','w') as f:
        f.write(text)

    if args.get_questions:
        # Crucially, we will need to chunk the data
        document = parse_raw(text,content_type,chunk=True)
        for subsection in document:
            with open('etc.out','a') as f:
                print(subsection,file=f)
                print('--------',file=f)
            generate_questions(subsection)

    with open('out.txt','w') as f:
        f.write(parse_raw(text,content_type))
    
    print('Execution complete!')
    