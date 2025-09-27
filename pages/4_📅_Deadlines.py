import streamlit as st, re
from ui_utils import load_css, uploader_block
from nlp_tasks import extract_deadlines as _extract_deadlines

st.set_page_config(page_title="Deadlines", page_icon="📅", layout="wide")
load_css()
st.title("📅 Deadlines")

with st.sidebar:
    st.header("Options")
    ctx_len = st.slider("Context width (chars per side)", 40, 200, 80, 10)

text, source = uploader_block("📂 Upload / paste text to scan for dates")

colA, colB = st.columns([1,1])
with colA:
    run = st.button("📆 Extract Deadlines", type="primary")
with colB:
    clear = st.button("🗑️ Clear")

if clear:
    if "deadlines" in st.session_state:
        del st.session_state["deadlines"]
    st.experimental_rerun()

if "deadlines" not in st.session_state:
    st.session_state.deadlines = None

if run:
    if not text.strip():
        st.warning("Upload or paste text first.")
    else:
        dl = _extract_deadlines(text)
        if dl and len(dl) == 1 and dl[0].get("context") == "INSTALL_DATEPARSER":
            st.error("`dateparser` not installed. Run:  pip install dateparser")
        else:
            # trim context for display only
            for d in dl:
                ctx = d["context"]
                if len(ctx) > ctx_len * 2:
                    d["context"] = ctx[:ctx_len] + " … " + ctx[-ctx_len:]
            st.session_state.deadlines = dl

if st.session_state.deadlines is not None:
    if len(st.session_state.deadlines) == 0:
        st.info("No deadlines found.")
    else:
        st.subheader("Found")
        for i, d in enumerate(st.session_state.deadlines, start=1):
            line = f"**{i}.** {d['match']} — **{d['iso_date']}**"
            if d.get("time"): line += f" at **{d['time']}**"
            st.markdown(f'<div class="card">{line}<br><span class="small-muted">{d["context"]}</span></div>',
                        unsafe_allow_html=True)

        # CSV download
        csv_lines = ["match,iso_date,time,context"]
        def esc(s:str)->str: s=(s or "").replace('"','""'); return f"\"{s}\""
        for d in st.session_state.deadlines:
            csv_lines.append(",".join([esc(d["match"]), esc(d["iso_date"]), esc(d.get("time","")), esc(d["context"])]))
        st.download_button("⬇️ Download (.csv)", "\n".join(csv_lines), "deadlines.csv", "text/csv")
