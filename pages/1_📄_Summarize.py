import streamlit as st, re
from ui_utils import load_css, uploader_block
from nlp_tasks import summarize

st.set_page_config(page_title="Summarize", page_icon="📄", layout="wide")
load_css()
st.title("📄 Summarize")

with st.sidebar:
    st.header("Settings")
    engine_choice = st.radio("Engine", ["extractive (instant)", "neural (abstractive)"], index=0)
    target_words = st.slider("Target summary length (neural only)", 80, 300, 150, 10)
    max_chars_input = st.slider("Max input size (chars cap)", 4000, 20000, 12000, 1000)
    timeout_s = st.slider("Neural timeout (s)", 10, 60, 25, 5)

text, source = uploader_block()

colA, colB = st.columns([1,1])
with colA:
    run = st.button("✨ Summarize", type="primary")
with colB:
    clear = st.button("🗑️ Clear")

if clear:
    st.experimental_rerun()

if run:
    if not text:
        st.warning("Upload a PDF or paste text first.")
    else:
        text = re.sub(r"\s+", " ", text).strip()
        engine = "neural" if engine_choice.startswith("neural") else "extractive"
        with st.spinner("Summarizing…"):
            out = summarize(text=text, mode=engine, target_words=target_words,
                            max_chars_input=max_chars_input, timeout_s=float(timeout_s))

        st.subheader("Summary")
        st.markdown(f'<div class="card">{out["summary"] or "(No output)"}'
                    f'</div>', unsafe_allow_html=True)

        st.caption(f"Source: {source or '—'} • Backend: {out.get('backend', engine)} • "
                   f"Time: {out.get('stats',{}).get('time_s','—')}s • Chars in: {len(text)}")

        st.download_button("⬇️ Download (.txt)", out["summary"] or "", "summary.txt", "text/plain")
