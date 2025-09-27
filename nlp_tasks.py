# # nlp_tasks.py — Summarization-first (lean)
# from __future__ import annotations
# import re, hashlib, time
# from typing import List

# # ---------- lightweight helpers ----------
# def _hash(text: str) -> str:
#     return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

# def _sentences(txt: str) -> List[str]:
#     s = re.sub(r"\s+", " ", txt.strip())
#     parts = re.split(r"(?<=[\.!?])\s+(?=[A-Z0-9])", s)
#     return [p.strip() for p in parts if p.strip()]

# def _chunks_by_chars(sents: List[str], max_chars: int) -> List[str]:
#     if not sents:
#         return []
#     out, cur, n = [], [], 0
#     for s in sents:
#         if n + len(s) + 1 > max_chars and cur:
#             out.append(" ".join(cur))
#             cur, n = [s], len(s)
#         else:
#             cur.append(s); n += len(s) + 1
#     if cur: out.append(" ".join(cur))
#     return out

# # ---------- summarizer (lazy, cached in app) ----------
# _SUMMARY_MODELS = {
#     "fast": "t5-small",            # smallest + quickest
#     "quality": "google/flan-t5-base"  # slightly slower, better quality
# }

# _pipeline = None
# _active_model = None

# def _get_summarizer(model_name: str = "fast"):
#     """Lazy-load a HF pipeline for the chosen model."""
#     global _pipeline, _active_model
#     target = _SUMMARY_MODELS.get(model_name, _SUMMARY_MODELS["fast"])
#     if _pipeline is None or _active_model != target:
#         import importlib
#         transformers = importlib.import_module("transformers")
#         _pipeline = transformers.pipeline(
#             "summarization",
#             model=target,
#             tokenizer=target,
#             framework="pt",
#         )
#         _active_model = target
#     return _pipeline

# def summarize_text(
#     text: str,
#     target_words: int = 180,
#     max_chunk_chars: int = 2500,
#     model_name: str = "fast",
# ) -> dict:
#     """
#     Map-reduce summarization:
#       1) Split to char-limited chunks by sentence boundaries.
#       2) Summarize each chunk.
#       3) Summarize the concatenated partial summaries to target length.
#     Returns {summary, stats}.
#     """
#     t0 = time.time()
#     text = text.strip()
#     if not text:
#         return {"summary": "", "stats": {"chunks": 0, "time_s": 0.0}}

#     # small texts: single pass
#     if len(text) <= max_chunk_chars:
#         summarizer = _get_summarizer(model_name)
#         approx_tokens = max(60, min(220, int(target_words * 1.6)))
#         final = summarizer(
#             "summarize: " + text,
#             max_length=approx_tokens,
#             min_length=max(40, int(approx_tokens * 0.5)),
#             do_sample=False
#         )[0]["summary_text"]
#         return {"summary": final, "stats": {"chunks": 1, "time_s": round(time.time()-t0, 3)}}

#     # long texts: chunk -> partial -> reduce
#     sents = _sentences(text)
#     chunks = _chunks_by_chars(sents, max_chunk_chars)

#     summarizer = _get_summarizer(model_name)
#     partial = []
#     for ch in chunks:
#         out = summarizer(
#             "summarize: " + ch,
#             max_length=120,                  # compact partials
#             min_length=60,
#             do_sample=False
#         )[0]["summary_text"]
#         partial.append(out)

#     combined = " ".join(partial)
#     approx_tokens = max(80, min(240, int(target_words * 1.6)))
#     final = summarizer(
#         "summarize: " + combined,
#         max_length=approx_tokens,
#         min_length=max(50, int(approx_tokens * 0.5)),
#         do_sample=False
#     )[0]["summary_text"]

#     return {
#         "summary": final,
#         "stats": {
#             "chunks": len(chunks),
#             "time_s": round(time.time() - t0, 3),
#             "model": _active_model
#         }
#     }




# nlp_tasks.py — instant extractive + optional neural (with timeout)
from __future__ import annotations
import re, hashlib, time, concurrent.futures
from typing import List, Dict
import PyPDF2

# ---------------- Utilities ----------------
def _sentences(txt: str) -> List[str]:
    s = re.sub(r"\s+", " ", txt.strip())
    parts = re.split(r"(?<=[\.!?])\s+(?=[A-Z0-9])", s)
    return [p.strip() for p in parts if p.strip()]

def _truncate(text: str, max_chars: int) -> str:
    return text[:max_chars] if len(text) > max_chars else text

# ---------------- Extractive (instant) ----------------
# TextRank via sumy (fast, no model download)
# ---------------- Extractive (instant, no external deps) ----------------
def _extractive_summary(text: str, max_sentences: int = 6) -> str:
    """
    Simple extractive summarizer:
    1) Split into sentences (regex-based).
    2) Build a word frequency table (lowercased, alphanumeric tokens).
    3) Score each sentence by the sum of word frequencies (length-normalized).
    4) Return top-N sentences in original order.
    """
    import re
    sents = _sentences(text)
    if not sents:
        return ""

    # tokenize words
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    stop = set((
        "the a an and or but if while with into onto from of in on for to is are was were be been being "
        "this that these those it its their his her your our they you we i as at by not no do does did "
        "so such than then there here over under between within without about above below up down out "
        "can could should would may might will just only also more most many much few little very"
    ).split())
    freq = {}
    for w in words:
        if w in stop: 
            continue
        freq[w] = freq.get(w, 0) + 1

    # sentence scoring
    sent_scores = []
    for idx, s in enumerate(sents):
        tokens = re.findall(r"[A-Za-z0-9']+", s.lower())
        if not tokens:
            continue
        score = sum(freq.get(t, 0) for t in tokens) / (len(tokens) ** 0.6)  # slight length norm
        sent_scores.append((idx, s, score))

    if not sent_scores:
        return sents[0] if sents else ""

    # pick top-N by score, then restore original order
    top = sorted(sent_scores, key=lambda x: x[2], reverse=True)[:max_sentences]
    top_sorted = sorted(top, key=lambda x: x[0])
    return " ".join(s for _, s, _ in top_sorted)


# ---------------- Neural (optional) ----------------
# small & reasonably quick abstractive model
_NEURAL_MODEL = "sshleifer/distilbart-cnn-12-6"

def _chunk_by_chars(text: str, max_chars: int = 1800) -> List[str]:
    sents = _sentences(text)
    chunks, cur, n = [], [], 0
    for s in sents:
        if n + len(s) + 1 > max_chars and cur:
            chunks.append(" ".join(cur)); cur, n = [s], len(s)
        else:
            cur.append(s); n += len(s) + 1
    if cur: chunks.append(" ".join(cur))
    return chunks

def _neural_summarizer_init():
    import importlib
    tr = importlib.import_module("transformers")
    return tr.pipeline("summarization", model=_NEURAL_MODEL, tokenizer=_NEURAL_MODEL, framework="pt")

_NEURAL = None

def _get_neural():
    global _NEURAL
    if _NEURAL is None:
        _NEURAL = _neural_summarizer_init()
    return _NEURAL

def _neural_single_pass(text: str, max_len_tokens: int, min_len_tokens: int) -> str:
    pipe = _get_neural()
    out = pipe(text, max_length=max_len_tokens, min_length=min_len_tokens, do_sample=False)[0]["summary_text"]
    return out

def _neural_summary(text: str, target_words: int = 150, max_chunk_chars: int = 1800) -> str:
    text = text.strip()
    if not text:
        return ""
    # single pass for small text
    if len(text) <= max_chunk_chars:
        return _neural_single_pass("summarize: " + text,
                                   max_len_tokens=max(64, int(target_words * 1.4)),
                                   min_len_tokens=max(32, int(target_words * 0.6)))
    # map-reduce for longer text
    chunks = _chunk_by_chars(text, max_chunk_chars=max_chunk_chars)
    partials = []
    for ch in chunks:
        partials.append(_neural_single_pass("summarize: " + ch, max_len_tokens=96, min_len_tokens=48))
    combined = " ".join(partials)
    return _neural_single_pass("summarize: " + combined,
                               max_len_tokens=max(80, int(target_words * 1.4)),
                               min_len_tokens=max(40, int(target_words * 0.6)))

#--------------------------------------------
# ---------------- PDF text extraction ----------------
def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts text from a PDF file (all pages).
    """
    import PyPDF2
    text = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text.append(content)
    return "\n".join(text).strip()





# ---------------- Public API ----------------
def summarize(
    text: str,
    mode: str = "extractive",       # "extractive" (instant) | "neural"
    target_words: int = 150,
    max_chars_input: int = 12000,   # hard cap to protect latency
    timeout_s: float = 25.0,        # if neural exceeds this, auto-fallback
) -> Dict:
    """
    Returns: {"summary": str, "stats": {...}, "backend": "extractive|neural|fallback"}
    """
    t0 = time.time()
    text = _truncate(text, max_chars_input)

    if mode == "extractive":
        s = _extractive_summary(text, max_sentences=6)
        return {"summary": s, "backend": "extractive", "stats": {"time_s": round(time.time()-t0, 3)}}

    # neural with timeout + safe fallback
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_neural_summary, text, target_words, 1800)
            s = fut.result(timeout=timeout_s)
        return {"summary": s, "backend": "neural", "stats": {"time_s": round(time.time()-t0, 3)}}
    except Exception:
        # fallback to instant extractive if anything is slow/broken
        s = _extractive_summary(text, max_sentences=6)
        return {"summary": s, "backend": "fallback_extractive", "stats": {"time_s": round(time.time()-t0, 3)}}
    









    # -------------------------------------------------------
    # ---------- MCQ generation (lightweight, no heavy models) ----------
import re, random
from typing import List, Dict

def _nlp_sentences(txt: str) -> List[str]:
    s = re.sub(r"\s+", " ", txt.strip())
    return [p.strip() for p in re.split(r"(?<=[\.!?])\s+(?=[A-Z0-9])", s) if p.strip()]

_STOPWORDS_MCQ = set("""
the a an and or but if while with into onto from of in on for to is are was were be been being
this that these those it its their his her your our they you we i as at by not no do does did
so such than then there here over under between within without about above below up down out
can could should would may might will just only also more most many much few little very
""".split())

def _keywords_mcq(text: str, k: int = 40) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", text.lower())
    freq = {}
    for w in words:
        if w in _STOPWORDS_MCQ: 
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    return [w for w,_ in ranked[:k]]

def _distractors_mcq(answer: str, vocab: List[str], n: int = 3) -> List[str]:
    cand = [v for v in vocab if v.lower() != answer.lower() and abs(len(v) - len(answer)) <= 2]
    random.shuffle(cand)
    out = []
    for w in cand:
        if w not in out:
            out.append(w)
        if len(out) >= n:
            break
    base = ["method", "process", "system", "model", "metric", "dataset", "feature"]
    i = 0
    while len(out) < n:
        if base[i] != answer:
            out.append(base[i])
        i = (i + 1) % len(base)
    return out

def make_mcq(text: str, num_questions: int = 6, seed: int = 42) -> List[Dict]:
    """
    Returns list of {"question": str, "options": [str,...], "answer": str}
    """
    random.seed(seed)
    sents = _nlp_sentences(text)
    if not sents:
        return []
    vocab = _keywords_mcq(text, k=40)
    qs: List[Dict] = []
    used = set()

    for s in sents:
        if len(qs) >= num_questions:
            break
        hits = [kw for kw in vocab if re.search(rf"\b{re.escape(kw)}\b", s, re.I)]
        if not hits:
            continue
        answer = max(hits, key=len)
        if answer in used:
            continue
        used.add(answer)

        cloze = re.sub(rf"\b{re.escape(answer)}\b", "_____", s, flags=re.I)
        opts = [answer] + _distractors_mcq(answer, vocab, n=3)
        random.shuffle(opts)
        qs.append({"question": cloze, "options": opts, "answer": answer})

    return qs


# -------------------------------------------------

# ---------- Flashcard generation ----------
import re
from typing import List, Tuple

def make_flashcards(text: str, num_cards: int = 8) -> List[Tuple[str, str]]:
    """
    Generate flashcards (Q,A) pairs from the input text.
    Each card is a tuple: (question, answer).
    """
    sents = re.split(r'(?<=[.!?])\s+', text)  # split into sentences
    cards: List[Tuple[str, str]] = []

    for s in sents:
        s = s.strip()
        words = s.split()
        if len(words) < 6:
            continue

        # Heuristic: Use first part as Q and the full sentence as A
        if " is " in s:
            parts = s.split(" is ", 1)
            q = f"What is {parts[0].strip()}?"
            a = s
        elif " was " in s:
            parts = s.split(" was ", 1)
            q = f"What was {parts[0].strip()}?"
            a = s
        elif " are " in s:
            parts = s.split(" are ", 1)
            q = f"What are {parts[0].strip()}?"
            a = s
        else:
            # fallback: first 6 words as Q
            q = "Complete this: " + " ".join(words[:6]) + " ..."
            a = s

        cards.append((q, a))

        if len(cards) >= num_cards:
            break

    return cards


# ------------------------------------------------
# ---------- Deadline extraction ----------
import re# ---------- Deadline extraction ----------
# import re
from typing import List, Dict
from datetime import datetime

# Regex catches: 17/09/2025, 17-09-25, Sep 17 2025, 17 Sep, Oct 13, by Friday, due 24/09, on 2025-09-24, etc.
_DATE_PATTERNS = re.compile(
    r"""
    (?P<prefix>\bby\b|\bdue\b|\bdeadline\b|\bon\b|\bbefore\b|\bsubmit\b|\bsubmission\b|\bdue\s+on\b)?\s*
    (?P<date>
        # ISO-like
        \d{4}-\d{1,2}-\d{1,2} |
        # 17/09/2025 or 17/09/25 or 17-09-2025
        \d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})? |
        # Sep 17 2025 | September 17, 2025 | 17 Sep 2025
        (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)
        \s+\d{1,2}(?:,\s*\d{2,4}|\s+\d{2,4})? |
        \d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)
        (?:\s+\d{2,4})?
    )
    (?:\s*(?:at|by)?\s*(?P<time>\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

def _context_window(text: str, start: int, end: int, window: int = 60) -> str:
    a = max(0, start - window)
    b = min(len(text), end + window)
    snippet = text[a:b].strip()
    return re.sub(r"\s+", " ", snippet)

def extract_deadlines(text: str) -> List[Dict]:
    """
    Extract date-like strings and normalize them to ISO dates.
    Returns list of dicts: {"match", "iso_date", "time", "context"}.
    """
    try:
        import dateparser
    except ImportError:
        return [{"match": "", "iso_date": "", "time": "", "context": "INSTALL_DATEPARSER"}]

    results: List[Dict] = []
    for m in _DATE_PATTERNS.finditer(text):
        raw_prefix = (m.group("prefix") or "").strip()
        raw_date = (m.group("date") or "").strip()
        raw_time = (m.group("time") or "").strip()
        raw_full = f"{raw_prefix} {raw_date} {raw_time}".strip()

        # SAFE parse: handle versions of dateparser that reject RELATIVE_BASE=None
        try:
            dt = dateparser.parse(
                raw_full,
                settings={
                    "PREFER_DATES_FROM": "future",
                    "RETURN_AS_TIMEZONE_AWARE": False,
                    "PARSERS": ["absolute-time", "relative-time", "custom-formats"],
                },
            )
        except TypeError:
            dt = dateparser.parse(
                raw_full,
                settings={
                    "PREFER_DATES_FROM": "future",
                    "RETURN_AS_TIMEZONE_AWARE": False,
                },
            )

        if dt:
            iso = dt.date().isoformat()
            results.append({
                "match": raw_full,
                "iso_date": iso,
                "time": raw_time,
                "context": _context_window(text, m.start(), m.end(), window=80),
            })

    # Deduplicate
    seen = set()
    deduped = []
    for r in results:
        key = (r["iso_date"], r["time"], r["match"].lower())
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped
