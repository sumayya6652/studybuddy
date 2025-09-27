import streamlit as st, re
from ui_utils import load_css, uploader_block
from nlp_tasks import make_mcq

st.set_page_config(page_title="Quiz", page_icon="🧩", layout="wide")
load_css()
st.title("🧩 Quiz")

with st.sidebar:
    st.header("Quiz Settings")
    num_q = st.slider("Number of questions", 3, 12, 6, 1)
    seed = st.number_input("Random seed", value=42, step=1)

text, source = uploader_block("📂 Upload / paste text for quiz")

# Session state
if "quiz_qs" not in st.session_state:
    st.session_state.quiz_qs = None
    st.session_state.quiz_answers = {}
    st.session_state.quiz_checked = False

col1, col2, col3 = st.columns([1,1,1])
with col1: gen = st.button("🧩 Generate Quiz", type="primary")
with col2: check = st.button("✅ Check Answers")
with col3: reset = st.button("🔄 New Quiz")

if reset:
    st.session_state.quiz_qs = None
    st.session_state.quiz_answers = {}
    st.session_state.quiz_checked = False

if gen:
    if not text.strip():
        st.warning("Upload or paste text first.")
    else:
        with st.spinner("Creating questions…"):
            qs = make_mcq(re.sub(r"\s+"," ", text), num_questions=int(num_q), seed=int(seed))
        if not qs:
            st.error("Could not generate questions. Try more/longer text.")
        else:
            st.session_state.quiz_qs = qs
            st.session_state.quiz_answers = {}
            st.session_state.quiz_checked = False

# Render
if st.session_state.quiz_qs:
    for i, q in enumerate(st.session_state.quiz_qs, start=1):
        st.markdown(f'<div class="card"><b>Q{i}.</b> {q["question"]}</div>', unsafe_allow_html=True)
        sel = st.radio("Select one", q["options"], key=f"q_{i}", label_visibility="collapsed")
        st.session_state.quiz_answers[f"q_{i}"] = sel
        if st.session_state.quiz_checked:
            if sel == q["answer"]:
                st.success(f"Correct ✓ Answer: **{q['answer']}**")
            else:
                st.error(f"Incorrect ✗ Your choice: **{sel}** • Correct: **{q['answer']}**")
        st.divider()

if check and st.session_state.quiz_qs:
    correct = sum(1 for i, q in enumerate(st.session_state.quiz_qs, start=1)
                  if st.session_state.quiz_answers.get(f"q_{i}") == q["answer"])
    total = len(st.session_state.quiz_qs)
    st.session_state.quiz_checked = True
    st.success(f"Score: {correct} / {total}")
