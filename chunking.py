from typing import Callable, Iterator, Optional, Set
from bs4 import BeautifulSoup
import re

class SoupCan:

    def __init__(self, body : BeautifulSoup, min_tokens : int = 2, max_tokens : int = 8192, stringify : Callable[[BeautifulSoup],str] = lambda s: s.get_text()):
        self.body = body
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.stringify = stringify

    def count_tokens(self,node = None):
        # TODO enable multiple tokenization modes
        if node is None:
            if self.current is None:
                return 0
            node = self.current
        text = self.stringify(node)
        text = text.replace('\n',' ')
        text = re.sub(r'([.,/\'"\[\]\(\)\\<>;:&=!?$@%#*+-])',r' \1 ',text)
        text = re.sub(r'\s+',r' ',text)
        return len(text.split(' '))

    def __iter__(self) -> Iterator[str]:
        self.current : Optional[BeautifulSoup] = self.body
        self.visited : Set[BeautifulSoup] = set()
        return self

    def __next__(self) -> str:
        if self.current is None:
            raise StopIteration

        # First, determine the 
        while self.current != self.body or self.current not in self.visited:
            #print('#',self.current)
            assert self.current is not None
            # If already visited, get sibling or return to parent
            if self.current in self.visited:
                if self.current.next_sibling is not None:
                    self.current = self.current.next_sibling
                else:
                    self.current = self.current.parent
                continue

            # If token count exceeds limit, dive down to children
            if self.count_tokens() > self.max_tokens:
                self.visited.add(self.current)
                self.current = self.current.contents[0]
                self.fresh = True
                continue

            # Merge consecutive elements that are too small
            # TODO maybe make greedy
            if self.count_tokens() <= self.max_tokens:
                self.visited.add(self.current)
                out_node = self.current
                while self.count_tokens(out_node) < self.min_tokens and self.current.next_sibling is not None:
                    self.current = self.current.next_sibling
                    if self.count_tokens(self.current) > self.max_tokens:
                        continue
                    self.visited.add(self.current)
                    out_node = BeautifulSoup(str(out_node)+'\n'+str(self.current),'html.parser')

                if self.current.next_sibling is not None:
                    self.current = self.current.next_sibling
                elif self.count_tokens(out_node) < self.min_tokens:
                    self.current = self.current.parent
                    continue
                else:
                    self.current = self.current.parent
                out = self.stringify(out_node)
                return out
            
        self.current = None
        # This flag is for the language model to determine
        return "### END OF DOCUMENT"


