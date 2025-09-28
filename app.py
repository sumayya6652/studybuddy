


# app.py — single-file UI with same-tab navigation (no new tabs)
import streamlit as st
import re
from ui_utils import load_css, uploader_block
from nlp_tasks import summarize, make_mcq, make_flashcards, extract_deadlines

# ---------------- Page Config ----------------
st.set_page_config(page_title="StudyMate — NLP Toolkit", page_icon="🧠", layout="wide")
load_css()

# ---------------- Extra CSS (nav bar styling) ----------------
st.markdown("""
<style>
/* Top nav row */
.navbar {
  display: grid; 
  grid-template-columns: repeat(5, 1fr);
  gap: 18px; 
  margin: 20px 0;
}

/* Make Streamlit buttons look like gradient cards */
.navbar .stButton>button {
  width: 100%;
  border-radius: 16px;
  font-size: 1.05rem;
  font-weight: 600;
  padding: 20px;
  color: white;
  cursor: pointer;
  border: none;
  transition: transform .15s ease, box-shadow .25s ease;
}
.navbar .stButton>button:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 22px rgba(0,0,0,0.35);
}

/* Gradient colors */
.navbar .col-home    .stButton>button { background: linear-gradient(135deg,#9d50bb,#6e48aa); }
.navbar .col-sum     .stButton>button { background: linear-gradient(135deg,#007bff,#00c6ff); }
.navbar .col-quiz    .stButton>button { background: linear-gradient(135deg,#ff7eb3,#ff758c); }
.navbar .col-flash   .stButton>button { background: linear-gradient(135deg,#43e97b,#38f9d7); color:#001; }
.navbar .col-dead    .stButton>button { background: linear-gradient(135deg,#f7971e,#ffd200); color:#221; }

/* Active outline */
.navbar .active .stButton>button {
  outline: 3px solid rgba(255,255,255,0.6);
}
</style>
""", unsafe_allow_html=True)


# ---------------- State: current page ----------------
if "page" not in st.session_state:
    st.session_state.page = "Home"

# Sync from query params (new Streamlit API)
if "page" in st.query_params:
    st.session_state.page = st.query_params["page"]

# ---------------- Top Navigation (buttons; same-tab) ----------------
st.markdown('<div class="navbar">', unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.markdown('<div class="col-home {}">'.format("active" if st.session_state.page=="Home" else ""), unsafe_allow_html=True)
    if st.button("🏠 Home", use_container_width=True):
        st.query_params.page = "Home"
        st.session_state.page = "Home"
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="col-sum {}">'.format("active" if st.session_state.page=="Summarize" else ""), unsafe_allow_html=True)
    if st.button("📄 Summarize", use_container_width=True):
        st.query_params.page = "Summarize"
        st.session_state.page = "Summarize"
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="col-quiz {}">'.format("active" if st.session_state.page=="Quiz" else ""), unsafe_allow_html=True)
    if st.button("🧩 Quiz", use_container_width=True):
        st.query_params.page = "Quiz"
        st.session_state.page = "Quiz"
    st.markdown('</div>', unsafe_allow_html=True)

with c4:
    st.markdown('<div class="col-flash {}">'.format("active" if st.session_state.page=="Flashcards" else ""), unsafe_allow_html=True)
    if st.button("🃏 Flashcards", use_container_width=True):
        st.query_params.page = "Flashcards"
        st.session_state.page = "Flashcards"
    st.markdown('</div>', unsafe_allow_html=True)

with c5:
    st.markdown('<div class="col-dead {}">'.format("active" if st.session_state.page=="Deadlines" else ""), unsafe_allow_html=True)
    if st.button("📅 Deadlines", use_container_width=True):
        st.query_params.page = "Deadlines"
        st.session_state.page = "Deadlines"
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Current choice
choice = st.session_state.page

# ---------------- Pages ----------------

# --- Home ---
if choice == "Home":
    st.title("🧠 StudyMate — NLP Toolkit")
    st.caption("Summarize • Quiz • Flashcards • Deadlines")
    st.markdown("""
    <div class="card">
      <h3>Welcome!</h3>
      <p class="small-muted">
        Upload a PDF or paste text, then switch tools with the colorful buttons above.
        StudyMate can generate summaries, quizzes, flashcards, and extract important deadlines.
      </p>
    </div>
    """, unsafe_allow_html=True)

# --- Summarizer ---
elif choice == "Summarize":
    st.header("📄 Summarizer")
    with st.sidebar:
        st.header("Summarizer Settings")
        engine_choice = st.radio("Engine", ["extractive (instant)", "neural (abstractive)"], index=0)
        target_words = st.slider("Target words (neural only)", 80, 300, 150, 10)
        max_chars_input = st.slider("Max input size", 4000, 20000, 12000, 1000)
        timeout_s = st.slider("Neural timeout (s)", 10, 60, 25, 5)

    text, source = uploader_block()
    if st.button("✨ Summarize", type="primary"):
        if not text.strip():
            st.warning("Upload or paste text first.")
        else:
            text = re.sub(r"\s+", " ", text).strip()
            engine = "neural" if engine_choice.startswith("neural") else "extractive"
            with st.spinner("Summarizing…"):
                out = summarize(
                    text=text,
                    mode=engine,
                    target_words=target_words,
                    max_chars_input=max_chars_input,
                    timeout_s=float(timeout_s),
                )
            st.subheader("Summary")
            st.markdown(f'<div class="card">{out["summary"] or "(No output)"}</div>', unsafe_allow_html=True)

# --- Quiz ---
elif choice == "Quiz":
    st.header("🧩 Quiz")
    with st.sidebar:
        st.header("Quiz Settings")
        num_q = st.slider("Number of questions", 3, 12, 6, 1)
        seed = st.number_input("Random seed", value=42, step=1)

    text, source = uploader_block("📂 Upload / paste text for quiz")
    if st.button("🧩 Generate Quiz", type="primary"):
        if not text.strip():
            st.warning("Upload or paste text first.")
        else:
            with st.spinner("Generating…"):
                qs = make_mcq(re.sub(r"\s+"," ", text), num_questions=int(num_q), seed=int(seed))
            if not qs:
                st.error("Could not generate questions.")
            else:
                st.session_state.quiz_qs = qs
                st.session_state.quiz_answers = {}
                st.session_state.quiz_checked = False

    if "quiz_qs" in st.session_state and st.session_state.quiz_qs:
        for i, q in enumerate(st.session_state.quiz_qs, start=1):
            st.markdown(f'<div class="card"><b>Q{i}.</b> {q["question"]}</div>', unsafe_allow_html=True)
            sel = st.radio("Select one", q["options"], key=f"q_{i}", label_visibility="collapsed")
            st.session_state.quiz_answers[f"q_{i}"] = sel

        if st.button("✅ Check Answers"):
            correct = sum(
                1 for i, q in enumerate(st.session_state.quiz_qs, start=1)
                if st.session_state.quiz_answers.get(f"q_{i}") == q["answer"]
            )
            total = len(st.session_state.quiz_qs)
            st.success(f"Score: {correct}/{total}")

# --- Flashcards ---
elif choice == "Flashcards":
    st.header("🃏 Flashcards")
    with st.sidebar:
        st.header("Flashcard Settings")
        num_cards = st.slider("Number of cards", 3, 15, 6, 1)

    text, source = uploader_block("📂 Upload / paste text for flashcards")
    if st.button("🃏 Generate Flashcards", type="primary"):
        if not text.strip():
            st.warning("Upload or paste text first.")
        else:
            cards = make_flashcards(text, num_cards=num_cards)  # returns list of (Q,A)
            st.session_state.flashcards = cards
            st.session_state.idx = 0
            st.session_state.flipped = False

    if "flashcards" in st.session_state and st.session_state.flashcards:
        q, a = st.session_state.flashcards[st.session_state.idx]
        flipped_class = "is-flipped" if st.session_state.flipped else ""
        st.markdown(f"""
        <div class="flip-wrap">
          <div class="flip-card {flipped_class}">
            <div class="flip-face flip-front">
              <div>
                <div class="small-muted">Question</div>
                <h4 style="margin-top:6px;">{q}</h4>
              </div>
            </div>
            <div class="flip-face flip-back">
              <div>
                <div class="small-muted">Answer</div>
                <p style="margin-top:6px;">{a}</p>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("⬅️ Prev"):
                if st.session_state.idx > 0:
                    st.session_state.idx -= 1
                    st.session_state.flipped = False
        with col2:
            if st.button("🔄 Flip"):
                st.session_state.flipped = not st.session_state.flipped
        with col3:
            if st.button("➡️ Next"):
                if st.session_state.idx < len(st.session_state.flashcards)-1:
                    st.session_state.idx += 1
                    st.session_state.flipped = False

# --- Deadlines ---
elif choice == "Deadlines":
    st.header("📅 Deadlines")
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
            dl = extract_deadlines(text)
            if dl and len(dl) == 1 and dl[0].get("context") == "INSTALL_DATEPARSER":
                st.error("`dateparser` not installed. Run:  pip install dateparser")
            else:
                for d in dl:
                    ctx = d["context"]
                    if len(ctx) > ctx_len * 2:
                        d["context"] = ctx[:ctx_len] + " … " + ctx[-ctx_len:]
                st.session_state.deadlines = dl

    if st.session_state.deadlines is not None:
        if len(st.session_state.deadlines) == 0:
            st.info("No deadlines found.")
        else:
            st.subheader("Found deadlines")
            for i, d in enumerate(st.session_state.deadlines, start=1):
                line = f"**{i}.** {d['match']} — **{d['iso_date']}**"
                if d.get("time"):
                    line += f" at **{d['time']}**"
                st.markdown(
                    f'<div class="card">{line}<br>'
                    f'<span class="small-muted">{d["context"]}</span></div>',
                    unsafe_allow_html=True,
                )

            # CSV download
            csv_lines = ["match,iso_date,time,context"]
            def esc(s: str) -> str:
                s = (s or "").replace('"','""')
                return f"\"{s}\""
            for d in st.session_state.deadlines:
                csv_lines.append(",".join([
                    esc(d["match"]),
                    esc(d["iso_date"]),
                    esc(d.get("time","")),
                    esc(d["context"])
                ]))
            st.download_button(
                "⬇️ Download deadlines (.csv)",
                "\n".join(csv_lines),
                "deadlines.csv",
                "text/csv"
            )
