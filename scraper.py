from bs4 import BeautifulSoup
from markdownify import markdownify as md
from dotenv import load_dotenv
import requests
from requests.exceptions import *
import argparse
import re
import os

load_dotenv()

def get(url : str):
    try:
        res = requests.get(url)
        content_type = res.headers['Content-Type'].split(';')[0]
        return res.text, content_type
    except SSLError:
        print("SSL certificate verification failed. Retrying without verification...")
        res = requests.get(url,verify=False)
        content_type = res.headers['Content-Type'].split(';')[0]
        return res.text, content_type

def parse_raw(raw_text, content_type='text/html'):
    match content_type:
        case 'text/html':
            soupcan = BeautifulSoup(raw_text,'html.parser')
            body_candidates = soupcan.find_all(class_=re.compile(r'((b|B)ody-?(c|C)ontent|(c|C)ontent-?(a|A)rea)')) # TODO identify possible ID/class tags
            body = body_candidates[0] if len(body_candidates) > 0 else soupcan.body
            parsed_text = md(body.prettify()) #soupcan.get_text()
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
        generate_questions()

    with open('out.txt','w') as f:
        f.write(parse_raw(text,content_type))
    
    print('Execution complete!')
    