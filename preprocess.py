import re
from typing import List, Tuple

SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')

def clean_text(t: str) -> str:
    t = t.replace("\xa0", " ").replace("\r", " ")
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{2,}', '\n', t)
    return t.strip()

def split_sentences(t: str) -> List[str]:
    t = clean_text(t)
    sents = SENT_SPLIT.split(t)
    return [s.strip() for s in sents if s.strip()]

def make_chunks(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    sents = split_sentences(text)
    chunks, cur = [], ""
    for s in sents:
        if len(cur) + len(s) + 1 <= chunk_size:
            cur = (cur + " " + s).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = cur[-overlap:] + " " + s if overlap > 0 else s
    if cur:
        chunks.append(cur.strip())
    # dedupe short tails
    return [c for i, c in enumerate(chunks) if c and (i == 0 or c != chunks[i-1])]
