



# nlp_tasks.py — core NLP + LLM + web helpers for StudyMate
# ----------------------------------------------------------
# Features:
#  - summarize(): extractive / neural / llm
#  - make_mcq(), make_mcq_llm()
#  - make_flashcards(), make_flashcards_llm()
#  - extract_deadlines(), extract_deadlines_llm()
#  - extract_text_from_pdf()
#  - make_report_llm(): build report with web context
#  - save_report_pdf(): export markdown to PDF

import os, re, time, json, tempfile, textwrap, hashlib, concurrent.futures
from typing import List, Dict, Any, Optional
from datetime import datetime

# =========================
# OpenAI client (with fallback to hard-coded key)
# =========================
OPENAI_MODEL_DEFAULT = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY_HARDCODED = ""   # <- put your key here for local use

def _get_openai_client():
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY") or OPENAI_API_KEY_HARDCODED
    if not api_key:
        raise RuntimeError("No API key found. Set OPENAI_API_KEY or fill OPENAI_API_KEY_HARDCODED.")
    return OpenAI(api_key=api_key)

def _call_llm_text(system_prompt: str, user_prompt: str, model: Optional[str] = None, max_output_tokens: int = 800) -> str:
    client = _get_openai_client()
    model = model or OPENAI_MODEL_DEFAULT
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_output_tokens=max_output_tokens,
    )
    return (resp.output_text or "").strip()

def _call_llm_json(system_prompt: str, user_prompt: str, model: Optional[str] = None, max_output_tokens: int = 1200) -> Any:
    txt = _call_llm_text(
        "You are a careful JSON-only generator. Output valid JSON. " + system_prompt,
        user_prompt,
        model=model,
        max_output_tokens=max_output_tokens,
    )
    # attempt to locate JSON in text
    try:
        # strip code fences if present
        txt2 = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip(), flags=re.IGNORECASE)
        return json.loads(txt2)
    except Exception:
        # last-ditch: find {...} block
        m = re.search(r"\{.*\}", txt, flags=re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        raise ValueError(f"LLM did not return valid JSON: {txt[:400]}...")

# =========================
# Utilities
# =========================
def _sentences(txt: str) -> List[str]:
    s = re.sub(r"\s+", " ", txt.strip())
    parts = re.split(r"(?<=[\.!?])\s+(?=[A-Z0-9])", s)
    return [p.strip() for p in parts if p.strip()]

def _truncate(text: str, max_chars: int) -> str:
    return text[:max_chars] if len(text) > max_chars else text

# =========================
# Extractive Summary (no external model)
# =========================
def _extractive_summary(text: str, max_sentences: int = 6) -> str:
    sents = _sentences(text)
    if not sents:
        return ""

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

    scored = []
    for idx, s in enumerate(sents):
        toks = re.findall(r"[A-Za-z0-9']+", s.lower())
        if not toks: 
            continue
        score = sum(freq.get(t, 0) for t in toks) / (len(toks) ** 0.6)
        scored.append((idx, s, score))
    if not scored:
        return sents[0] if sents else ""
    top = sorted(scored, key=lambda x: x[2], reverse=True)[:max_sentences]
    top = sorted(top, key=lambda x: x[0])
    return " ".join(s for _, s, _ in top)

# =========================
# Neural Summarizer (DistilBART)
# =========================
_NEURAL_MODEL = "sshleifer/distilbart-cnn-12-6"
_NEURAL = None

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
    if len(text) <= max_chunk_chars:
        return _neural_single_pass("summarize: " + text,
                                   max_len_tokens=max(64, int(target_words * 1.4)),
                                   min_len_tokens=max(32, int(target_words * 0.6)))
    chunks = _chunk_by_chars(text, max_chunk_chars=max_chunk_chars)
    partials = []
    for ch in chunks:
        partials.append(_neural_single_pass("summarize: " + ch, max_len_tokens=96, min_len_tokens=48))
    combined = " ".join(partials)
    return _neural_single_pass("summarize: " + combined,
                               max_len_tokens=max(80, int(target_words * 1.4)),
                               min_len_tokens=max(40, int(target_words * 0.6)))

# =========================
# PDF Text Extraction
# =========================
def extract_text_from_pdf(file_path: str) -> str:
    import PyPDF2
    text = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text.append(content)
    return "\n".join(text).strip()

# =========================
# Public Summarize API (supports 'extractive' | 'neural' | 'llm')
# =========================
def summarize(
    text: str,
    mode: str = "extractive",
    target_words: int = 150,
    max_chars_input: int = 12000,
    timeout_s: float = 25.0,
) -> Dict:
    t0 = time.time()
    text = _truncate(text, max_chars_input)

    if mode == "extractive":
        s = _extractive_summary(text, max_sentences=6)
        return {"summary": s, "backend": "extractive", "stats": {"time_s": round(time.time()-t0, 3)}}

    if mode == "llm":
        sys = "You write clear, study-friendly summaries in 1-2 paragraphs."
        usr = f"Summarize this for a student (about {target_words} words):\n\n{text}"
        try:
            s = _call_llm_text(sys, usr, model=OPENAI_MODEL_DEFAULT, max_output_tokens=600)
            return {"summary": s, "backend": "llm", "stats": {"time_s": round(time.time()-t0, 3)}}
        except Exception:
            # fallback to extractive on LLM errors
            s = _extractive_summary(text, max_sentences=6)
            return {"summary": s, "backend": "fallback_extractive", "stats": {"time_s": round(time.time()-t0, 3)}}

    # neural with timeout + fallback
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(_neural_summary, text, target_words, 1800)
            s = fut.result(timeout=timeout_s)
        return {"summary": s, "backend": "neural", "stats": {"time_s": round(time.time()-t0, 3)}}
    except Exception:
        s = _extractive_summary(text, max_sentences=6)
        return {"summary": s, "backend": "fallback_extractive", "stats": {"time_s": round(time.time()-t0, 3)}}

# =========================
# MCQ Generators
# =========================
def make_mcq(text: str, num_questions: int = 6, seed: int = 42) -> List[Dict[str, Any]]:
    # simple keyword/cloze-like generator (baseline)
    import random
    random.seed(seed)
    sents = [s for s in _sentences(text) if len(s.split()) > 6]
    if not sents: return []
    qs = []
    for s in random.sample(sents, min(num_questions, len(sents))):
        words = re.findall(r"[A-Za-z][A-Za-z\-']+", s)
        words = [w for w in words if len(w) > 4]
        if len(words) < 1: 
            continue
        ans = random.choice(words)
        stem = s.replace(ans, "____", 1)
        # distractors: pick nearby words
        pool = [w for w in set(words) if w.lower() != ans.lower()]
        random.shuffle(pool)
        opts = [ans] + pool[:3]
        random.shuffle(opts)
        qs.append({"question": stem, "options": opts, "answer": ans})
    return qs

def make_mcq_llm(text: str, num_questions: int = 6, seed: int = 42) -> List[Dict[str, Any]]:
    sys = "You write concise MCQs. Always return JSON: {\"questions\":[{\"question\":\"...\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"answer\":\"...\"}]}"
    usr = f"Text:\n{text}\n\nGenerate {num_questions} MCQs with 4 options each and the correct 'answer'."
    out = _call_llm_json(sys, usr, model=OPENAI_MODEL_DEFAULT, max_output_tokens=1600)
    qs = out.get("questions", [])
    # sanitize
    clean = []
    for q in qs:
        try:
            opts = [str(o) for o in q["options"]][:4]
            if len(opts) < 2: 
                continue
            clean.append({"question": str(q["question"]), "options": opts, "answer": str(q["answer"])})
        except Exception:
            continue
    return clean[:num_questions]

# =========================
# Flashcards
# =========================
def make_flashcards(text: str, num_cards: int = 6) -> List[List[str]]:
    sents = _sentences(text)
    if not sents: return []
    cards = []
    for s in sents[: num_cards * 2]:
        # naive Q/A: turn statement into question
        q = re.sub(r"\.$", "?", s)
        if not q.endswith("?"): q += "?"
        a = s
        cards.append([q, a])
        if len(cards) >= num_cards: break
    return cards

def make_flashcards_llm(text: str, num_cards: int = 6) -> List[Dict[str, str]]:
    sys = "You produce short Q/A flashcards. Return JSON: {\"cards\":[{\"question\":\"...\",\"answer\":\"...\"}]}"
    usr = f"Make {num_cards} flashcards (short question + short answer) from:\n{text}"
    out = _call_llm_json(sys, usr, model=OPENAI_MODEL_DEFAULT, max_output_tokens=1200)
    cards = out.get("cards", [])
    clean = []
    for c in cards:
        q = str(c.get("question","")).strip()
        a = str(c.get("answer","")).strip()
        if q and a:
            clean.append({"question": q, "answer": a})
    return clean[:num_cards]

# =========================
# Deadlines
# =========================
def extract_deadlines(text: str) -> List[Dict[str, str]]:
    """
    Robust non-LLM deadline extractor.
    Uses dateparser.search.search_dates to find explicit dates in free text,
    captures a short context snippet, and extracts hh:mm if present.
    """
    try:
        from datetime import datetime
        import dateparser
        from dateparser.search import search_dates
    except Exception:
        return [{"match": "", "iso_date": "", "time": "", "context": "INSTALL_DATEPARSER"}]

    s = (text or "").strip()
    if not s:
        return []

    # settings tuned for assignments / forward-looking dates
    settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": datetime.now(),
        "RETURN_AS_TIMEZONE_AWARE": False,
    }

    results: List[Dict[str, str]] = []

    try:
        matches = search_dates(s, languages=None, settings=settings)  # -> [(matched_str, datetime), ...]
    except Exception:
        matches = None

    if matches:
        for mstr, dt in matches:
            if not dt:
                continue

            # Find position of the matched text to extract context
            span = None
            for mm in re.finditer(re.escape(mstr), s, flags=re.IGNORECASE):
                span = (mm.start(), mm.end())
                break

            ctx = ""
            if span:
                ctx_start = max(0, span[0] - 80)
                ctx_end   = min(len(s), span[1] + 80)
                ctx = s[ctx_start:ctx_end]

            # Optional hh:mm inside the matched string
            tmatch = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", mstr)
            hhmm = f"{int(tmatch.group(1)):02d}:{int(tmatch.group(2)):02d}" if tmatch else ""

            results.append({
                "match": mstr.strip(),
                "iso_date": dt.date().isoformat(),
                "time": hhmm,
                "context": ctx,
            })

    # de-dupe on (iso_date, match)
    uniq, seen = [], set()
    for d in results:
        key = (d["iso_date"], d["match"].lower())
        if key in seen:
            continue
        seen.add(key)
        # ensure strings (avoid None later)
        d["context"] = d.get("context") or ""
        d["time"] = d.get("time") or ""
        d["match"] = d.get("match") or ""
        uniq.append(d)

    return uniq

def extract_deadlines_llm(text: str) -> List[Dict[str, str]]:
    sys = "Extract deadlines as JSON list with objects: {match, iso_date, time, context}."
    usr = f"Text:\n{text}\n\nReturn JSON {{\"deadlines\":[...]}} with 0+ items."
    out = _call_llm_json(sys, usr, model=OPENAI_MODEL_DEFAULT, max_output_tokens=1600)
    return out.get("deadlines", [])

# =========================
# Web Research (DuckDuckGo via ddgs + trafilatura)
# =========================
def _web_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    # prefer ddgs; fallback to duckduckgo_search if present
    results = []
    try:
        from ddgs import DDGS  # new package name
    except Exception:
        from duckduckgo_search import DDGS  # legacy
    with DDGS() as ddg:
        for r in ddg.text(query, max_results=max_results):
            url = r.get("href") or r.get("url")
            if not url:
                continue
            results.append({"title": r.get("title",""), "url": url})
    return results[:max_results]

def _fetch_article_text(url: str, max_chars: int = 6000) -> str:
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if not downloaded: 
            return ""
        txt = trafilatura.extract(downloaded, include_comments=False, include_tables=False) or ""
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt[:max_chars]
    except Exception:
        return ""

# =========================
# Report (LLM + Web)
# =========================
def make_report_llm(notes_text: str, topic: Optional[str] = None, max_sources: int = 5, target_words: int = 1200) -> Dict[str, Any]:
    """
    Builds an extended study report:
      - infer key topics from notes (if no topic provided)
      - search web, fetch a few reputable sources
      - draft a structured report with citations (inline [1], [2], ...)
    Returns: {"report_md": str, "sources": [{"title","url"}...]}
    """
    base = re.sub(r"\s+", " ", (notes_text or "")).strip()
    if not base:
        return {"report_md": "", "sources": []}

    # 1) If topic hint not provided, ask LLM to infer search topics
    if not topic:
        sys = "You pick concise search topics for studying given notes. Return JSON: {\"topics\":[\"...\"]}"
        usr = f"Notes:\n{base[:4000]}\n\nPropose 3-5 short search topics."
        try:
            out = _call_llm_json(sys, usr, model=OPENAI_MODEL_DEFAULT, max_output_tokens=600)
            topics = out.get("topics", [])
        except Exception:
            topics = []
        if not topics:
            # fallback: quick keywords
            tokens = [t for t in re.findall(r"[A-Za-z][A-Za-z\-']+", base.lower()) if len(t) > 3]
            topics = list(dict.fromkeys(tokens))[:4]
    else:
        topics = [topic]

    # 2) Web search & fetch
    picked = []
    for t in topics:
        for r in _web_search(t, max_results=2):
            if len(picked) >= max_sources: break
            art = _fetch_article_text(r["url"])
            if len(art) > 400:
                picked.append({"title": r["title"], "url": r["url"], "text": art})
        if len(picked) >= max_sources: break

    # 3) Draft report with LLM (give it notes + snippets)
    sources_for_llm = "\n\n".join([f"[{i+1}] {s['title']} — {s['url']}\n{s['text'][:1200]}" for i, s in enumerate(picked)])
    sys = (
        "You are an expert study assistant. Write a cohesive, student-friendly report in Markdown with:\n"
        "- Title & short abstract\n- Key concepts explained clearly\n- Worked examples or analogies\n"
        "- Short FAQ\n- Further reading list\nUse inline citations like [1], [2] referring to the sources list."
    )
    usr = (
        f"Student notes (cleaned):\n{base[:8000]}\n\n"
        f"Relevant sources (snippets, numbered):\n{sources_for_llm}\n\n"
        f"Write a {target_words}±20% word report that covers the notes and fills gaps using the sources. "
        f"Keep it accurate, readable, and well-structured. End with a numbered Sources section."
    )
    report_md = _call_llm_text(sys, usr, model=OPENAI_MODEL_DEFAULT, max_output_tokens=3000)

    # 4) Prepare sources list for UI
    sources_meta = [{"title": s["title"], "url": s["url"]} for s in picked]
    return {"report_md": report_md, "sources": sources_meta}

# =========================
# Save Markdown → PDF (simple)
# =========================
def save_report_pdf(markdown_text: str, pdf_path: str):
    """
    Minimal Markdown-to-PDF using reportlab. (No images/links rendering.)
    Produces a clean, printable study handout.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    # strip basic MD symbols for PDF text layout
    txt = markdown_text or ""
    txt = re.sub(r"`{1,3}.*?`{1,3}", " ", txt)
    txt = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", txt)
    txt = re.sub(r"^#+\s*", "", txt, flags=re.M)
    txt = re.sub(r"[*_~>#-]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()

    c = canvas.Canvas(pdf_path, pagesize=A4)
    W, H = A4
    x, y = 2*cm, H - 2*cm
    c.setTitle("Study Report")

    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, y, "Study Report"); y -= 22
    c.setFont("Helvetica", 9)
    c.drawString(x, y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"); y -= 16

    c.setFont("Helvetica", 11)
    width_chars = 100  # wrap approx
    for para in txt.split("\n"):
        lines = textwrap.wrap(para, width=width_chars) if para.strip() else [""]
        for line in lines:
            c.drawString(x, y, line); y -= 14
            if y < 3*cm:
                c.showPage()
                y = H - 2*cm
                c.setFont("Helvetica", 11)
        y -= 4

    c.save()
