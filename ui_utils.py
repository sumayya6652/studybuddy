# ui_utils.py
import streamlit as st
import tempfile, re
from typing import Tuple, Optional
from nlp_tasks import extract_text_from_pdf  # your existing function

CSS = """
<style>
/* Page width + global tweaks */
.main .block-container {max-width: 1100px;}

/* Fancy section headers */
h1, h2, h3 { letter-spacing: 0.3px; }

/* Primary action buttons */
.stButton>button[kind="primary"]{
  border-radius: 14px;
  padding: 10px 18px;
  box-shadow: 0 6px 16px rgba(31,111,235,0.35);
  transition: transform .12s ease, box-shadow .2s ease;
}
.stButton>button[kind="primary"]:hover{
  transform: translateY(-1px);
  box-shadow: 0 8px 22px rgba(31,111,235,0.45);
}

/* Card */
.card {
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.04));
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.35);
  backdrop-filter: blur(6px);
}

/* Quiz option pills */
.option-pill{
  display:inline-block; margin:6px 8px 0 0; padding:8px 12px; border-radius:999px;
  border:1px solid rgba(255,255,255,0.12);
  transition: background .15s ease, transform .08s ease;
}
.option-pill:hover{ background: rgba(255,255,255,0.06); transform: translateY(-1px); }

/* Flip card for flashcards */
.flip-wrap { perspective: 1200px; }
.flip-card {
  position: relative; width: 100%; min-height: 140px;
  transform-style: preserve-3d; transition: transform 0.6s ease;
}
.flip-card.is-flipped { transform: rotateY(180deg); }
.flip-face {
  position:absolute; inset:0; backface-visibility: hidden;
  border-radius: 16px; padding: 18px; display:flex; align-items:center;
  border:1px solid rgba(255,255,255,0.08);
  box-shadow: 0 8px 24px rgba(0,0,0,0.35);
}
.flip-front{ background: #111a2a; }
.flip-back{ background: #0e1726; transform: rotateY(180deg); }
.flip-actions button{
  margin-right: 8px;
}
.small-muted { color:#a3b1c6; font-size: 0.92rem; }
</style>
"""

def load_css():
    st.markdown(CSS, unsafe_allow_html=True)

def uploader_block(label: str="📂 Upload a PDF or paste text") -> Tuple[str, Optional[str]]:
    """Unified uploader used by all pages. Returns (text, source)."""
    st.subheader(label)
    col1, col2 = st.columns([1,1])
    source = None
    text = ""

    with col1:
        uploaded = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
        if uploaded is not None:
            with st.spinner("Reading PDF…"):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uploaded.read())
                    path = tmp.name
                pdf_text = extract_text_from_pdf(path)
                pdf_text = re.sub(r"\s+", " ", (pdf_text or "")).strip()
                if pdf_text:
                    text, source = pdf_text, "pdf"
                    st.success(f"Extracted {len(pdf_text)} characters from PDF.")
                else:
                    st.warning("PDF seems to contain little/no extractable text (maybe scanned images).")

    with col2:
        manual = st.text_area("Or paste text here", height=200, placeholder="Paste notes / transcript / paper text...")
        if manual and manual.strip():
            text, source = manual.strip(), "manual"

    return text, source
