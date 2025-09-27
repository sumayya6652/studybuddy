
# # app.py — Summarization-first UI with instant default + neural option# app.py — StudyMate Summarizer (PDF + Text, Extractive default, Neural optional)
# import streamlit as st
# import tempfile
# from nlp_tasks import summarize, extract_text_from_pdf  # make sure these exist in nlp_tasks.py

# # ---------------- Page config ----------------
# st.set_page_config(page_title="StudyMate — Summarizer", page_icon="📝", layout="wide")
# st.title("📝 StudyMate — Summarizer")

# # ---------------- Sidebar: settings ----------------
# with st.sidebar:
#     st.header("Settings")

#     engine_choice = st.radio(
#         "Engine",
#         options=["extractive (instant)", "neural (abstractive)"],
#         index=0,
#         help=(
#             "Instant = fast extractive (no model download). "
#             "Neural = DistilBART (may download weights on first use, has timeout + fallback)."
#         ),
#     )

#     target_words = st.slider(
#         "Target summary length (words) — neural only",
#         min_value=80,
#         max_value=300,
#         value=150,
#         step=10,
#         help="Only used when Engine=neural. Extractive mode ignores this.",
#     )

#     max_chars_input = st.slider(
#         "Max input size (characters cap)",
#         min_value=4000,
#         max_value=20000,
#         value=12000,
#         step=1000,
#         help="Protects latency by truncating very large inputs.",
#     )

#     timeout_s = st.slider(
#         "Neural timeout (seconds)",
#         min_value=10,
#         max_value=60,
#         value=25,
#         step=5,
#         help="If neural exceeds this, it auto-falls back to instant extractive.",
#     )

#     clean_spaces = st.checkbox(
#         "Normalize whitespace",
#         value=True,
#         help="Collapses repeated spaces/newlines in extracted text before summarizing.",
#     )

# # ---------------- Input area ----------------
# st.subheader("Input")

# # 1) PDF uploader
# uploaded_file = st.file_uploader("📂 Upload a PDF file", type=["pdf"])

# pdf_text = ""
# if uploaded_file is not None:
#     with st.spinner("Reading PDF…"):
#         with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#             tmp.write(uploaded_file.read())
#             pdf_path = tmp.name
#         try:
#             pdf_text = extract_text_from_pdf(pdf_path)
#             if clean_spaces:
#                 import re
#                 pdf_text = re.sub(r"\s+", " ", pdf_text).strip()
#             st.success(f"Extracted {len(pdf_text)} characters from PDF.")
#         except Exception as e:
#             st.error(f"Failed to read PDF: {e}")

# # 2) Manual text box
# manual_text = st.text_area("Or paste text here:", height=260, placeholder="Paste long text…")

# # Decide which text to use (manual overrides PDF if provided)
# source = None
# text_to_summarize = ""
# if manual_text.strip():
#     source = "manual"
#     text_to_summarize = manual_text.strip()
# elif pdf_text.strip():
#     source = "pdf"
#     text_to_summarize = pdf_text.strip()

# # ---------------- Actions ----------------
# colA, colB = st.columns([1, 1])
# with colA:
#     run = st.button("✨ Summarize", type="primary")
# with colB:
#     clear = st.button("🗑️ Clear")

# if clear:
#     st.experimental_rerun()

# # ---------------- Summarize ----------------
# if run:
#     if not text_to_summarize:
#         st.warning("Please upload a PDF or paste some text first.")
#     else:
#         if clean_spaces:
#             import re
#             text_to_summarize = re.sub(r"\s+", " ", text_to_summarize).strip()

#         engine = "neural" if engine_choice.startswith("neural") else "extractive"

#         with st.spinner("Summarizing…"):
#             out = summarize(
#                 text=text_to_summarize,
#                 mode=engine,
#                 target_words=target_words,
#                 max_chars_input=max_chars_input,
#                 timeout_s=float(timeout_s),
#             )

#         st.subheader("Summary")
#         st.write(out["summary"] or "_(No summary produced — try adding a bit more input.)_")

#         st.divider()
#         st.caption(
#             f"Source: {source or '—'} • "
#             f"Backend: {out.get('backend', engine)} • "
#             f"Time: {out.get('stats', {}).get('time_s', '—')}s • "
#             f"Chars in: {len(text_to_summarize)}"
#         )

#         st.download_button(
#             "⬇️ Download summary (.txt)",
#             data=out["summary"] or "",
#             file_name="summary.txt",
#             mime="text/plain",
#         )

# # ---------------- Optional: Roadmap (for poster/report) ----------------
# with st.expander("Roadmap"):
#     st.markdown(
#         "- **MVP (this):** PDF/Text summarization (extractive default, neural optional with timeout and fallback).\n"
#         "- **Next:** MCQ generation (keyword/cloze; on-click, not preloaded).\n"
#         "- **Later:** Flashcards & deadline extraction (optional enhancements)."
#     )





# app.py — StudyMate: Summarizer (your original) + MCQ Quiz (added)
import streamlit as st
import tempfile
import re

# --- IMPORTS ---
from nlp_tasks import summarize, extract_text_from_pdf  # existing
from nlp_tasks import make_mcq  # NEW: lightweight MCQ generator you added to nlp_tasks.py

# ---------------- Page config ----------------
st.set_page_config(page_title="StudyMate — Summarizer", page_icon="📝", layout="wide")
st.title("📝 StudyMate — Summarizer")

# ---------------- Sidebar: settings ----------------
with st.sidebar:
    st.header("Settings")

    engine_choice = st.radio(
        "Engine",
        options=["extractive (instant)", "neural (abstractive)"],
        index=0,
        help=(
            "Instant = fast extractive (no model download). "
            "Neural = DistilBART (may download weights on first use, has timeout + fallback)."
        ),
    )

    target_words = st.slider(
        "Target summary length (words) — neural only",
        min_value=80,
        max_value=300,
        value=150,
        step=10,
        help="Only used when Engine=neural. Extractive mode ignores this.",
    )

    max_chars_input = st.slider(
        "Max input size (characters cap)",
        min_value=4000,
        max_value=20000,
        value=12000,
        step=1000,
        help="Protects latency by truncating very large inputs.",
    )

    timeout_s = st.slider(
        "Neural timeout (seconds)",
        min_value=10,
        max_value=60,
        value=25,
        step=5,
        help="If neural exceeds this, it auto-falls back to instant extractive.",
    )

    clean_spaces = st.checkbox(
        "Normalize whitespace",
        value=True,
        help="Collapses repeated spaces/newlines in extracted text before summarizing.",
    )

# ---------------- Input area ----------------
st.subheader("Input")

# 1) PDF uploader
uploaded_file = st.file_uploader("📂 Upload a PDF file", type=["pdf"])

pdf_text = ""
if uploaded_file is not None:
    with st.spinner("Reading PDF…"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            pdf_path = tmp.name
        try:
            pdf_text = extract_text_from_pdf(pdf_path)
            if clean_spaces:
                pdf_text = re.sub(r"\s+", " ", pdf_text).strip()
            st.success(f"Extracted {len(pdf_text)} characters from PDF.")
        except Exception as e:
            st.error(f"Failed to read PDF: {e}")

# 2) Manual text box
manual_text = st.text_area("Or paste text here:", height=260, placeholder="Paste long text…")

# Decide which text to use (manual overrides PDF if provided)
source = None
text_to_summarize = ""
if manual_text.strip():
    source = "manual"
    text_to_summarize = manual_text.strip()
elif pdf_text.strip():
    source = "pdf"
    text_to_summarize = pdf_text.strip()

# ---------------- Actions ----------------
colA, colB = st.columns([1, 1])
with colA:
    run = st.button("✨ Summarize", type="primary")
with colB:
    clear = st.button("🗑️ Clear")

if clear:
    st.experimental_rerun()

# ---------------- Summarize ----------------
if run:
    if not text_to_summarize:
        st.warning("Please upload a PDF or paste some text first.")
    else:
        if clean_spaces:
            text_to_summarize = re.sub(r"\s+", " ", text_to_summarize).strip()

        engine = "neural" if engine_choice.startswith("neural") else "extractive"

        with st.spinner("Summarizing…"):
            out = summarize(
                text=text_to_summarize,
                mode=engine,
                target_words=target_words,
                max_chars_input=max_chars_input,
                timeout_s=float(timeout_s),
            )

        st.subheader("Summary")
        st.write(out["summary"] or "_(No summary produced — try adding a bit more input.)_")

        st.divider()
        st.caption(
            f"Source: {source or '—'} • "
            f"Backend: {out.get('backend', engine)} • "
            f"Time: {out.get('stats', {}).get('time_s', '—')}s • "
            f"Chars in: {len(text_to_summarize)}"
        )

        st.download_button(
            "⬇️ Download summary (.txt)",
            data=out["summary"] or "",
            file_name="summary.txt",
            mime="text/plain",
        )

# ---------------- Optional: Roadmap (for poster/report) ----------------
with st.expander("Roadmap"):
    st.markdown(
        "- **MVP (this):** PDF/Text summarization (extractive default, neural optional with timeout and fallback).\n"
        "- **Next:** MCQ generation (keyword/cloze; on-click, not preloaded).\n"
        "- **Later:** Flashcards & deadline extraction (optional enhancements)."
    )

# ======================================================================
# ========================== MCQ QUIZ (NEW) =============================
# ======================================================================

st.markdown("---")
st.header("❓ Quiz")

# Session state for quiz
if "quiz_qs" not in st.session_state:
    st.session_state.quiz_qs = None
    st.session_state.quiz_answers = {}
    st.session_state.quiz_checked = False
    st.session_state.quiz_score = 0

# Controls
col_q1, col_q2, col_q3 = st.columns([1, 1, 1])
with col_q1:
    num_q = st.slider("Number of questions", 3, 12, 6, 1, key="num_q_slider")
with col_q2:
    seed = st.number_input("Random seed", value=42, step=1, key="seed_num")
with col_q3:
    gen_btn = st.button("🧩 Generate Quiz", type="primary", key="gen_quiz_btn")

col_c1, col_c2 = st.columns([1, 1])
with col_c1:
    check_btn = st.button("✅ Check Answers", key="check_btn")
with col_c2:
    reset_btn = st.button("🔄 New Quiz", key="reset_btn")

# Reset quiz
if reset_btn:
    st.session_state.quiz_qs = None
    st.session_state.quiz_answers = {}
    st.session_state.quiz_checked = False
    st.session_state.quiz_score = 0

# Generate quiz from the SAME input used for summarizer
if gen_btn:
    if not text_to_summarize or not text_to_summarize.strip():
        st.warning("Upload a PDF or paste text first (used for both summary and quiz).")
    else:
        with st.spinner("Creating questions…"):
            qs = make_mcq(text_to_summarize, num_questions=int(num_q), seed=int(seed))
        if not qs:
            st.error("Could not generate questions. Try more/longer text.")
        else:
            st.session_state.quiz_qs = qs
            st.session_state.quiz_answers = {}
            st.session_state.quiz_checked = False
            st.session_state.quiz_score = 0

# Render quiz
if st.session_state.quiz_qs:
    st.subheader("Answer the questions")
    for i, q in enumerate(st.session_state.quiz_qs, start=1):
        key = f"q_{i}"
        # keep selection if user already chose something
        current_index = None
        if key in st.session_state.quiz_answers:
            try:
                current_index = q["options"].index(st.session_state.quiz_answers[key])
            except ValueError:
                current_index = None

        sel = st.radio(
            f"**Q{i}.** {q['question']}",
            options=q["options"],
            index=current_index,
            key=key,
        )
        if sel is not None:
            st.session_state.quiz_answers[key] = sel

        if st.session_state.quiz_checked:
            correct = q["answer"]
            user = st.session_state.quiz_answers.get(key)
            if user is None:
                st.info(f"Answer: **{correct}**")
            elif user == correct:
                st.success(f"Correct ✓  Answer: **{correct}**")
            else:
                st.error(f"Incorrect ✗  Your choice: **{user}** • Correct: **{correct}**")
        st.divider()

# Check answers
if check_btn and st.session_state.quiz_qs:
    score = 0
    total = len(st.session_state.quiz_qs)
    for i, q in enumerate(st.session_state.quiz_qs, start=1):
        if st.session_state.quiz_answers.get(f"q_{i}") == q["answer"]:
            score += 1
    st.session_state.quiz_score = score
    st.session_state.quiz_checked = True
    st.success(f"Score: {score} / {total}")

# Export quiz
if st.session_state.quiz_qs:
    export_lines = []
    for i, q in enumerate(st.session_state.quiz_qs, start=1):
        opts = "\n".join([f"  - {o}" for o in q["options"]])
        export_lines.append(f"Q{i}. {q['question']}\n{opts}\nAnswer: {q['answer']}\n")
    st.download_button(
        "⬇️ Download quiz (.txt)",
        data="\n".join(export_lines),
        file_name="quiz.txt",
        mime="text/plain",
        key="dl_quiz_btn"
    )





# ======================================================================
# ========================== FLASHCARDS (NEW) ==========================
# ======================================================================

st.markdown("---")
st.header("🃏 Flashcards")

if "flashcards" not in st.session_state:
    st.session_state.flashcards = None
    st.session_state.current_card = 0
    st.session_state.show_answer = False

col_f1, col_f2 = st.columns([1,1])
with col_f1:
    num_cards = st.slider("Number of flashcards", 3, 15, 6, 1, key="num_cards_slider")
with col_f2:
    gen_fc = st.button("🃏 Generate Flashcards", type="primary", key="gen_fc_btn")

if gen_fc:
    if not text_to_summarize.strip():
        st.warning("Upload a PDF or paste text first.")
    else:
        from nlp_tasks import make_flashcards
        cards = make_flashcards(text_to_summarize, num_cards=num_cards)
        if not cards:
            st.error("Could not generate flashcards. Try more/longer text.")
        else:
            st.session_state.flashcards = cards
            st.session_state.current_card = 0
            st.session_state.show_answer = False

# Display flashcards
if st.session_state.flashcards:
    card = st.session_state.flashcards[st.session_state.current_card]
    st.subheader(f"Card {st.session_state.current_card+1}/{len(st.session_state.flashcards)}")

    if st.session_state.show_answer:
        st.success(card["answer"])
    else:
        st.info(card["question"])

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("⬅️ Previous", key="prev_fc"):
            if st.session_state.current_card > 0:
                st.session_state.current_card -= 1
                st.session_state.show_answer = False
    with c2:
        if st.button("🔄 Flip", key="flip_fc"):
            st.session_state.show_answer = not st.session_state.show_answer
    with c3:
        if st.button("➡️ Next", key="next_fc"):
            if st.session_state.current_card < len(st.session_state.flashcards)-1:
                st.session_state.current_card += 1
                st.session_state.show_answer = False


# --------------------------------------------
# ======================================================================
# ======================= DEADLINE EXTRACTION (NEW) =====================
# ======================================================================

st.markdown("---")
st.header("📅 Deadlines")

col_d1, col_d2 = st.columns([1,1])
with col_d1:
    extract_btn = st.button("📆 Extract Deadlines", type="primary", key="btn_deadlines")
with col_d2:
    ctx_words = st.slider("Context window (chars)", 40, 200, 80, 10, key="dl_ctx")

if "deadlines" not in st.session_state:
    st.session_state.deadlines = None

if extract_btn:
    if not text_to_summarize or not text_to_summarize.strip():
        st.warning("Upload a PDF or paste text first.")
    else:
        # call the extractor
        from nlp_tasks import extract_deadlines as _extract_deadlines
        dl = _extract_deadlines(text_to_summarize)
        # handle missing dependency nicely
        if dl and len(dl) == 1 and dl[0].get("context") == "INSTALL_DATEPARSER":
            st.error("`dateparser` not installed. Run:  pip install dateparser")
            st.stop()

        # Optionally trim context length on display
        for d in dl:
            if len(d["context"]) > ctx_words * 2:
                # center around the match by cutting equally on both sides
                # (this is display-only; raw extraction kept full context)
                d["context"] = d["context"][:ctx_words] + " … " + d["context"][-ctx_words:]

        st.session_state.deadlines = dl

# Render deadlines
if st.session_state.deadlines:
    if len(st.session_state.deadlines) == 0:
        st.info("No deadlines found.")
    else:
        st.subheader("Found deadlines")
        for i, d in enumerate(st.session_state.deadlines, start=1):
            st.markdown(
                f"**{i}.** {d['match']}  \n"
                f"- ISO date: `{d['iso_date']}`{' • Time: `'+d['time']+'`' if d['time'] else ''}  \n"
                f"- Context: _{d['context']}_"
            )
            st.divider()

        # Build CSV (no pandas needed)
        csv_lines = ["match,iso_date,time,context"]
        def _csv_escape(s: str) -> str:
            s = (s or "").replace('"', '""')
            return f"\"{s}\""
        for d in st.session_state.deadlines:
            csv_lines.append(
                ",".join([
                    _csv_escape(d["match"]),
                    _csv_escape(d["iso_date"]),
                    _csv_escape(d["time"]),
                    _csv_escape(d["context"]),
                ])
            )
        csv_data = "\n".join(csv_lines)
        st.download_button(
            "⬇️ Download deadlines (.csv)",
            data=csv_data,
            file_name="deadlines.csv",
            mime="text/csv",
            key="dl_deadlines_csv"
        )
