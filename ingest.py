from typing import Tuple
import os, io, re, requests
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text
from preprocess import clean_text

def from_pdf(path: str) -> Tuple[str, str]:
    raw = extract_text(path) or ""
    return os.path.basename(path), clean_text(raw)

def from_text_string(name: str, text: str) -> Tuple[str, str]:
    return name, clean_text(text)

def from_url(url: str) -> Tuple[str, str]:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for s in soup(["script", "style", "noscript"]):
        s.extract()
    txt = re.sub(r'\n{2,}', '\n', soup.get_text(separator="\n"))
    return url, clean_text(txt)
