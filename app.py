





# app.py — StudyMate (page functions to prevent bleed)
import streamlit as st
import re, os, tempfile
from datetime import datetime
from ui_utils import load_css, uploader_block
from nlp_tasks import (
    summarize,
    make_mcq, make_mcq_llm,
    make_flashcards, make_flashcards_llm,
    extract_deadlines, extract_deadlines_llm,
    make_report_llm, save_report_pdf  

)

# ---------------- Page Config ----------------
st.set_page_config(page_title="StudyMate — NLP Toolkit", page_icon="🧠", layout="wide")
load_css()

# ---------------- TTS helpers ----------------
def tts_say(text: str, filename_prefix: str = "voice"):
    """gTTS → MP3 (simple)"""
    if not text or not text.strip():
        return None
    try:
        from gtts import gTTS
        mp3_path = os.path.join(tempfile.gettempdir(), f"{filename_prefix}_{next(tempfile._get_candidate_names())}.mp3")
        gTTS(text.strip(), lang="en").save(mp3_path)
        return mp3_path
    except Exception as e:
        st.error(f"TTS failed: {e}")
        return None

def tts_say_single_wav(text: str, fname_prefix: str = "summary_onefile"):
    """pyttsx3 → single WAV (offline, no chunking)"""
    if not text or not text.strip():
        return None
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 180)
        engine.setProperty("volume", 1.0)
        wav_path = os.path.join(
            tempfile.gettempdir(),
            f"{fname_prefix}_{next(tempfile._get_candidate_names())}.wav"
        )
        engine.save_to_file(text, wav_path)
        engine.runAndWait()
        return wav_path if os.path.exists(wav_path) else None
    except Exception as e:
        st.error(f"TTS failed: {e}")
        return None

# ---------------- Quiz helpers ----------------
def infer_topic_from_question(q: str) -> str:
    toks = re.findall(r"[A-Za-z][A-Za-z\-']+", q or "")
    stop = {
        "the","a","an","and","or","but","if","while","with","into","onto","from","of","in","on","for","to",
        "is","are","was","were","be","been","being","this","that","these","those","it","its","their","his",
        "her","your","our","they","you","we","as","at","by","not","no","do","does","did","so","such","than",
        "then","there","here","over","under","between","within","without","about","above","below","out"
    }
    toks = [t for t in toks if t.lower() not in stop]
    return " ".join(toks[:3]) if toks else "General"

def build_quiz_pdf(student_name: str, qs, answers_map, out_name="StudyMate_Quiz_Report.pdf"):
    """
    Detailed PDF:
     • Overall correct/wrong bar
     • Topic-wise accuracy bar
     • Summary of strong/weak topics
     • Question review
    """
    from collections import defaultdict
    import matplotlib.pyplot as plt
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    # --- compute stats ---
    total = len(qs)
    correct, wrong = 0, 0
    topic_stats = defaultdict(lambda: {"correct": 0, "total": 0})
    q_review = []  # (qtext, your, corr, right, topic)

    for i, q in enumerate(qs, start=1):
        topic = q.get("topic") or infer_topic_from_question(q["question"])
        your_ans = answers_map.get(f"q_{i}")
        right = (your_ans == q["answer"])
        topic_stats[topic]["total"] += 1
        if right:
            topic_stats[topic]["correct"] += 1
            correct += 1
        else:
            wrong += 1
        q_review.append((q["question"], your_ans or "—", q["answer"], right, topic))
        q["topic"] = topic

    # --- graphs ---
    tmp = tempfile.gettempdir()
    chart_overall = os.path.join(tmp, f"quiz_overall_{next(tempfile._get_candidate_names())}.png")
    chart_topics  = os.path.join(tmp, f"quiz_topics_{next(tempfile._get_candidate_names())}.png")

    # overall correct/wrong
    plt.figure(figsize=(3.8, 3))
    plt.bar(["Correct", "Wrong"], [correct, wrong], color=["#43e97b", "#ff758c"])
    plt.title("Overall Performance")
    plt.tight_layout()
    plt.savefig(chart_overall, dpi=150)
    plt.close()

    # per-topic accuracy
    topics = list(topic_stats.keys())
    acc = [round(100 * v["correct"] / v["total"], 1) for v in topic_stats.values()]
    plt.figure(figsize=(5, 3.5))
    plt.barh(topics, acc, color="#00c6ff")
    plt.xlabel("Accuracy (%)")
    plt.title("Topic-wise Accuracy")
    plt.tight_layout()
    plt.savefig(chart_topics, dpi=150)
    plt.close()

    # summaries
    strong = [t for t, v in topic_stats.items() if v["correct"] / v["total"] >= 0.8]
    weak   = [t for t, v in topic_stats.items() if v["correct"] / v["total"] < 0.5]
    summary_txt = []
    if strong: summary_txt.append(f"Strong topics: {', '.join(strong)}.")
    if weak:   summary_txt.append(f"Needs improvement: {', '.join(weak)}.")
    if not summary_txt: summary_txt.append("Performance balanced across topics.")
    summary_txt = " ".join(summary_txt)

    # --- PDF write ---
    pdf_path = os.path.join(tmp, out_name)
    c = canvas.Canvas(pdf_path, pagesize=A4)
    W, H = A4
    x, y = 2*cm, H - 2*cm

    c.setFont("Helvetica-Bold", 16); c.drawString(x, y, "StudyMate — Quiz Performance Report")
    y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(x, y, f"Student: {student_name or '—'}"); y -= 14
    c.drawString(x, y, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"); y -= 18
    c.setFont("Helvetica-Bold", 12); c.drawString(x, y, f"Score: {correct}/{total}  ({round(100*correct/total,1)}%)"); y -= 18

    # charts
    try:
        c.drawImage(chart_overall, x, y-7*cm, width=8*cm, height=6*cm, preserveAspectRatio=True); y -= 7*cm + 12
    except: pass
    try:
        c.drawImage(chart_topics,  x, y-7*cm, width=10*cm, height=6*cm, preserveAspectRatio=True); y -= 7*cm + 16
    except: pass

    c.setFont("Helvetica-Bold", 12); c.drawString(x, y, "Summary:"); y -= 14
    c.setFont("Helvetica", 11)
    for line in summary_txt.split(". "):
        c.drawString(x, y, line.strip()); y -= 14
        if y < 3*cm: c.showPage(); y = H - 3*cm; c.setFont("Helvetica", 11)

    # question review
    c.showPage(); y = H - 2*cm
    c.setFont("Helvetica-Bold", 14); c.drawString(x, y, "Question Review"); y -= 18
    c.setFont("Helvetica", 10)
    for qtext, your, corr, right, topic in q_review:
        mark = "✅" if right else "❌"
        line = f"{mark} {topic} | Your: {your} | Ans: {corr}"
        for seg in [qtext, line]:
            for chunk in [seg[i:i+95] for i in range(0, len(seg), 95)]:
                c.drawString(x, y, chunk); y -= 12
                if y < 3*cm: c.showPage(); y = H - 2*cm; c.setFont("Helvetica", 10)
        y -= 8

    c.save()
    return pdf_path

# ---------------- State: current page ----------------
if "page" not in st.session_state:
    st.session_state.page = "Home"

# keep URL shareable
if "page" in st.query_params:
    st.session_state.page = st.query_params["page"]

# ---------------- Sidebar: Student ----------------
st.sidebar.header("👤 Student")
student_name = st.sidebar.text_input("Your name", value=st.session_state.get("student_name", ""))
if student_name != st.session_state.get("student_name"):
    st.session_state["student_name"] = student_name

# ---------------- Top Nav CSS ----------------
st.markdown("""
<style>
.navbar { display: grid; grid-template-columns: repeat(5, 1fr); gap: 18px; margin: 20px 0; }
.navbar .stButton>button {
  width: 100%; border-radius: 16px; font-size: 1.05rem; font-weight: 600;
  padding: 20px; color: #fff; border: none; transition: transform .15s ease, box-shadow .25s ease;
}
.navbar .stButton>button:hover { transform: translateY(-3px); box-shadow: 0 10px 22px rgba(0,0,0,0.35); }
.col-home  .stButton>button { background: linear-gradient(135deg,#9d50bb,#6e48aa); }
.col-sum   .stButton>button { background: linear-gradient(135deg,#007bff,#00c6ff); }
.col-quiz  .stButton>button { background: linear-gradient(135deg,#ff7eb3,#ff758c); }
.col-flash .stButton>button { background: linear-gradient(135deg,#43e97b,#38f9d7); color:#001; }
.col-dead  .stButton>button { background: linear-gradient(135deg,#f7971e,#ffd200); color:#221; }
.navbar .active .stButton>button { outline: 3px solid rgba(255,255,255,0.6); }
.small-muted { color:#a3b1c6; font-size: 0.92rem; }
</style>
""", unsafe_allow_html=True)

# ---------------- Top Navigation ----------------
st.markdown('<div class="navbar">', unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown('<div class="col-home {}">'.format("active" if st.session_state.page=="Home" else ""), unsafe_allow_html=True)
    if st.button("🏠 Home", use_container_width=True):
        st.query_params.page = "Home"; st.session_state.page = "Home"
    st.markdown('</div>', unsafe_allow_html=True)
with c2:
    st.markdown('<div class="col-sum {}">'.format("active" if st.session_state.page=="Summarize" else ""), unsafe_allow_html=True)
    if st.button("📄 Summarize", use_container_width=True):
        st.query_params.page = "Summarize"; st.session_state.page = "Summarize"
    st.markdown('</div>', unsafe_allow_html=True)
with c3:
    st.markdown('<div class="col-quiz {}">'.format("active" if st.session_state.page=="Quiz" else ""), unsafe_allow_html=True)
    if st.button("🧩 Quiz", use_container_width=True):
        st.query_params.page = "Quiz"; st.session_state.page = "Quiz"
    st.markdown('</div>', unsafe_allow_html=True)
with c4:
    st.markdown('<div class="col-flash {}">'.format("active" if st.session_state.page=="Flashcards" else ""), unsafe_allow_html=True)
    if st.button("🃏 Flashcards", use_container_width=True):
        st.query_params.page = "Flashcards"; st.session_state.page = "Flashcards"
    st.markdown('</div>', unsafe_allow_html=True)
with c5:
    st.markdown('<div class="col-dead {}">'.format("active" if st.session_state.page=="Deadlines" else ""), unsafe_allow_html=True)
    if st.button("📅 Deadlines", use_container_width=True):
        st.query_params.page = "Deadlines"; st.session_state.page = "Deadlines"
    st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

choice = st.session_state.page

# =========================
# Page Renderers
# =========================
def render_home():
    st.title("🧠 StudyMate — NLP Toolkit")
    st.caption("Summarize • Quiz • Flashcards • Deadlines")
    st.markdown("""
    <div class="card">
      <h3>Welcome!</h3>
      <p class="small-muted">
        Voice buttons 🔊 will read content aloud. Enter your name in the left sidebar for a personalized quiz report.
      </p>
    </div>
    """, unsafe_allow_html=True)

def render_summarize():
    st.header("📄 Summarizer")
    with st.sidebar:
        st.header("Summarizer Settings")
        engine_choice = st.radio("Engine", ["extractive (instant)", "neural (abstractive)", "llm (OpenAI)"], index=0)
        target_words = st.slider("Target words (for neural/llm)", 80, 400, 150, 10)
        max_chars_input = st.slider("Max input size", 4000, 20000, 12000, 1000)
        timeout_s = st.slider("Timeout (s)", 10, 60, 25, 5)

        st.markdown("---")
        st.subheader("🧾 Report (LLM + Web)")
        topic_hint = st.text_input("Optional topic hint (improves search/structure)")
        max_sources = st.slider("Max web sources", 0, 8, 5, 1)
        report_words = st.slider("Target report length (words)", 400, 2500, 1200, 100)

    text, _ = uploader_block()

    # persistent summary + report
    ss = st.session_state
    ss.setdefault("summary_text", "")
    ss.setdefault("summary_audio_path", None)
    ss.setdefault("report_md", "")
    ss.setdefault("report_pdf_path", None)
    ss.setdefault("report_sources", [])

    # --- Summarize ---
    if st.button("✨ Summarize", type="primary"):
        if not (text or "").strip():
            st.warning("Upload or paste text first.")
        else:
            clean = re.sub(r"\s+", " ", text).strip()
            mode = "llm" if engine_choice.startswith("llm") else ("neural" if engine_choice.startswith("neural") else "extractive")
            with st.spinner("Summarizing…"):
                out = summarize(
                    text=clean,
                    mode=mode,
                    target_words=target_words,
                    max_chars_input=max_chars_input,
                    timeout_s=float(timeout_s),
                )
            ss.summary_text = out["summary"] or "(No output)"
            ss.summary_audio_path = None

    if ss.summary_text:
        st.subheader("Summary")
        st.markdown(
            f'<div class="card">{ss.summary_text}'
            f'<br><span class="small-muted">Text stays here even after you play audio.</span></div>',
            unsafe_allow_html=True
        )
        c1, c2 = st.columns([1,1])
        with c1:
            make_voice = st.button("🔊 Make & Play Voice")
        with c2:
            clear_voice = st.button("🗑️ Clear Voice")
        if clear_voice:
            st.session_state.summary_audio_path = None
            st.rerun()
        if make_voice:
            with st.spinner("Generating voice…"):
                path = tts_say_single_wav(ss.summary_text, "summary_onefile")
            if path: ss.summary_audio_path = path
        if ss.summary_audio_path:
            st.audio(ss.summary_audio_path)
    else:
        st.info("Upload/paste text and click **Summarize** to see your summary here.")

    st.markdown("---")

    # --- Summary Report (LLM + Web) ---
    st.subheader("🧾 Summary Report (adds web context)")
    colA, colB = st.columns([1,1])
    with colA:
        build_report = st.button("🧾 Build Summary Report", type="primary")
    with colB:
        clear_report = st.button("🗑️ Clear Report")

    if clear_report:
        ss.report_md = ""
        ss.report_pdf_path = None
        ss.report_sources = []
        st.rerun()

    if build_report:
        base_notes = (text or "").strip()
        if not base_notes:
            st.warning("Upload a PDF or paste notes before building the report.")
        else:
            with st.spinner("Researching + drafting report…"):
                result = make_report_llm(
                    base_notes,
                    topic=(topic_hint or None),
                    max_sources=int(max_sources),
                    target_words=int(report_words),
                )
            ss.report_md = result.get("report_md", "")
            ss.report_sources = result.get("sources", [])
            # save PDF
            
            if ss.report_md:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        pdf_path = tmp.name
                    save_report_pdf(ss.report_md, pdf_path)
                    ss.report_pdf_path = pdf_path
                    st.success("Report ready.")
                except Exception as e:
                    ss.report_pdf_path = None
                    st.error(f"Failed to generate PDF: {e}")

    if ss.report_md:
        st.markdown("#### Preview")
        st.markdown(ss.report_md)

        if ss.report_sources:
            st.markdown("**Sources used**")
            for i, s in enumerate(ss.report_sources, start=1):
                st.markdown(f"{i}. [{s.get('title','source')}]({s.get('url','')})")

        if ss.report_pdf_path:
            with open(ss.report_pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Download Report (.pdf)",
                    f.read(),
                    file_name="StudyMate_Summary_Report.pdf",
                    mime="application/pdf"
                )
def render_quiz():
    st.header("🧩 Quiz")
    with st.sidebar:
        st.header("Quiz Settings")
        num_q = st.slider("Number of questions", 3, 12, 6, 1)
        seed = st.number_input("Random seed", value=42, step=1)
        use_llm = st.checkbox("Use LLM generator", value=True)

    text, _ = uploader_block("📂 Upload / paste text for quiz")

    if st.button("🧩 Generate Quiz", type="primary"):
        if not (text or "").strip():
            st.warning("Upload or paste text first.")
        else:
            with st.spinner("Generating…"):
                qs = make_mcq_llm(re.sub(r"\s+"," ", text), num_questions=int(num_q), seed=int(seed)) if use_llm \
                     else make_mcq(re.sub(r"\s+"," ", text), num_questions=int(num_q), seed=int(seed))
            if not qs:
                st.error("Could not generate questions. Try longer/cleaner text.")
            else:
                for q in qs:
                    q["topic"] = infer_topic_from_question(q["question"])
                st.session_state.quiz_qs = qs
                st.session_state.quiz_answers = {}
                st.session_state.quiz_pdf_path = None
                st.success(f"Generated {len(qs)} questions.")

    if "quiz_qs" in st.session_state and st.session_state.quiz_qs:
        # Render questions
        for i, q in enumerate(st.session_state.quiz_qs, start=1):
            st.markdown(f'<div class="card"><b>Q{i}.</b> {q["question"]}</div>', unsafe_allow_html=True)
            try:
                sel = st.radio("Select one", q["options"], index=None, key=f"q_{i}", label_visibility="collapsed")
            except TypeError:
                opts = ["— choose —"] + q["options"]
                sel_raw = st.radio("Select one", opts, index=0, key=f"q_{i}", label_visibility="collapsed")
                sel = None if sel_raw == "— choose —" else sel_raw
            st.session_state.quiz_answers[f"q_{i}"] = sel
            if st.button(f"🔊 Read Q{i}", key=f"read_q_{i}"):
                mp3 = tts_say(f"Question {i}. {q['question']}. Options: {', '.join(q['options'])}", f"q_{i}")
                if mp3: st.audio(mp3)

        # Controls row (kept strictly inside Quiz page)
        colA, colB, colC = st.columns([1,1,1])
        with colA:
            check = st.button("✅ Check Answers", type="primary", key="quiz_check_btn")
        with colB:
            build_pdf = st.button("📄 Build PDF Report", key="quiz_build_pdf_btn")
        with colC:
            clear = st.button("🗑️ Clear Quiz", key="quiz_clear_btn")

        if clear:
            for k in list(st.session_state.keys()):
                if k.startswith("q_"): del st.session_state[k]
            st.session_state.pop("quiz_qs", None)
            st.session_state.pop("quiz_answers", None)
            st.session_state.pop("quiz_pdf_path", None)
            st.rerun()

        def _all_answered():
            total = len(st.session_state.quiz_qs)
            return all(st.session_state.quiz_answers.get(f"q_{i}") is not None for i in range(1, total+1))

        def _compute_score():
            correct = sum(
                1 for i, q in enumerate(st.session_state.quiz_qs, start=1)
                if st.session_state.quiz_answers.get(f"q_{i}") == q["answer"]
            )
            total = len(st.session_state.quiz_qs)
            return correct, total

        if check:
            if not _all_answered():
                st.warning("Please answer all questions before checking.")
            else:
                c,t = _compute_score()
                st.success(f"Score: {c}/{t}")

        if build_pdf:
            if not _all_answered():
                st.warning("Please answer all questions before building the report.")
            else:
                try:
                    pdf_path = build_quiz_pdf(
                        student_name=st.session_state.get("student_name",""),
                        qs=st.session_state.quiz_qs,
                        answers_map=st.session_state.quiz_answers,
                        out_name="StudyMate_Quiz_Report.pdf"
                    )
                    st.session_state.quiz_pdf_path = pdf_path
                    st.success("Report generated.")
                except Exception as e:
                    st.error(f"Failed to build PDF report: {e}")
                    st.session_state.quiz_pdf_path = None

        if st.session_state.get("quiz_pdf_path"):
            with open(st.session_state.quiz_pdf_path, "rb") as f:
                st.download_button(
                    "⬇️ Download Quiz Report (.pdf)",
                    f.read(),
                    file_name="StudyMate_Quiz_Report.pdf",
                    mime="application/pdf",
                    key="quiz_pdf_download_btn"
                )
    else:
        st.info("Generate a quiz to begin.")

def render_flashcards():
    st.header("🃏 Flashcards")
    with st.sidebar:
        st.header("Flashcard Settings")
        num_cards = st.slider("Number of cards", 3, 15, 6, 1)
        use_llm_fc = st.checkbox("Use LLM flashcards", value=True)

    text, _ = uploader_block("📂 Upload / paste text for flashcards")

    def _normalize_cards(raw):
        norm = []
        if not raw: return norm
        for item in raw:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                q, a = str(item[0]).strip(), str(item[1]).strip()
                if q and a: norm.append((q, a))
            elif isinstance(item, dict):
                q = str(item.get("question", item.get("q", ""))).strip()
                a = str(item.get("answer", item.get("a", ""))).strip()
                if q and a: norm.append((q, a))
            elif isinstance(item, str):
                s = item.strip()
                if s: norm.append((s, s))
        return norm

    ss = st.session_state
    if "flashcards" not in ss: ss.flashcards = []
    if "idx" not in ss: ss.idx = 0
    if "flipped" not in ss: ss.flipped = False
    if "fc_audio_path" not in ss: ss.fc_audio_path = None

    if st.button("🃏 Generate Flashcards", type="primary", key="fc_generate_btn"):
        if not (text or "").strip():
            st.warning("Upload or paste text first.")
        else:
            try:
                raw_cards = make_flashcards_llm(text, num_cards=num_cards) if use_llm_fc \
                            else make_flashcards(text, num_cards=num_cards)
            except TypeError:
                raw_cards = make_flashcards(text, max_cards=num_cards)
            except Exception as e:
                st.error(f"Flashcard generator crashed: {e}")
                raw_cards = []
            cards = _normalize_cards(raw_cards)
            if not cards:
                st.error("Could not generate flashcards. Try longer/cleaner text.")
            else:
                ss.flashcards = cards; ss.idx = 0; ss.flipped = False; ss.fc_audio_path = None
                st.success(f"Generated {len(cards)} flashcards.")

    def _clamp():
        if not ss.flashcards: ss.idx = 0; ss.flipped = False; return
        ss.idx = max(0, min(ss.idx, len(ss.flashcards)-1))

    def _fc_first(): ss.idx = 0; ss.flipped = False; ss.fc_audio_path=None; _clamp()
    def _fc_prev():  ss.idx -= 1; ss.flipped = False; ss.fc_audio_path=None; _clamp()
    def _fc_flip():  ss.flipped = not ss.flipped; ss.fc_audio_path=None; _clamp()
    def _fc_next():  ss.idx += 1; ss.flipped = False; ss.fc_audio_path=None; _clamp()
    def _fc_speak():
        if not ss.flashcards: return
        q, a = ss.flashcards[ss.idx]
        side = "Answer" if ss.flipped else "Question"
        txt = f"{side}: {a if ss.flipped else q}"
        path = tts_say_single_wav(txt, "flashcard_onefile"); ss.fc_audio_path = path

    cards = ss.flashcards
    if cards:
        _clamp()
        q, a = cards[ss.idx]
        flipped_class = "is-flipped" if ss.flipped else ""
        st.markdown(f"""
        <div class="flip-wrap">
          <div class="flip-card {flipped_class}">
            <div class="flip-face flip-front"><div><div class="small-muted">Question</div>
            <h4 style="margin-top:6px;">{q}</h4></div></div>
            <div class="flip-face flip-back"><div><div class="small-muted">Answer</div>
            <p style="margin-top:6px;">{a}</p></div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns([1,1,1,1,1])
        c1.button("⏮ First", key="fc_first_btn", on_click=_fc_first, use_container_width=True)
        c2.button("⬅️ Prev",  key="fc_prev_btn",  on_click=_fc_prev,  use_container_width=True, disabled=(ss.idx==0))
        c3.button("🔄 Flip",  key="fc_flip_btn",  on_click=_fc_flip, use_container_width=True)
        c4.button("➡️ Next",  key="fc_next_btn",  on_click=_fc_next, use_container_width=True, disabled=(ss.idx>=len(cards)-1))
        c5.button("🔊 Speak", key="fc_speak_btn", on_click=_fc_speak, use_container_width=True)

        st.caption(f"Card {ss.idx + 1} / {len(cards)}")
        if ss.get("fc_audio_path"):
            st.audio(ss.fc_audio_path, format="audio/wav")
    else:
        st.info("No flashcards yet. Paste text above and click **Generate Flashcards**.")

def render_deadlines():
    st.header("📅 Deadlines")
    with st.sidebar:
        st.header("Options")
        ctx_len = st.slider("Context width (chars per side)", 40, 200, 80, 10)
        use_llm_dl = st.checkbox("Use LLM deadline extractor", value=True)

    text, _ = uploader_block("📂 Upload / paste text to scan for dates")
    colA, colB, colC = st.columns([1,1,1])
    with colA: run = st.button("📆 Extract Deadlines", type="primary")
    with colB: clear = st.button("🗑️ Clear")
    with colC: speak_btn = st.button("🔊 Speak deadlines")

    if clear:
        st.session_state.pop("deadlines", None)
        st.rerun()

    st.session_state.setdefault("deadlines", None)

    if run:
        if not (text or "").strip():
            st.warning("Upload or paste text first.")
        else:
            with st.spinner("Finding dates…"):
                try:
                    dl = extract_deadlines_llm(text) if use_llm_dl else extract_deadlines(text)
                except Exception as e:
                    st.error(f"Deadline extractor failed: {e}")
                    dl = []
            if dl and len(dl) == 1 and (dl[0].get("context") == "INSTALL_DATEPARSER"):
                st.error("`dateparser` not installed. Run:  pip install dateparser")
            else:
                # — sanitize items so UI never crashes —
                safe_list = []
                for d in (dl or []):
                    match = d.get("match") or ""
                    iso_date = d.get("iso_date") or ""
                    tm = d.get("time") or ""
                    ctx = d.get("context") or ""
                    # trim context for display only
                    if ctx and isinstance(ctx, str) and len(ctx) > ctx_len * 2:
                        ctx = ctx[:ctx_len] + " … " + ctx[-ctx_len:]
                    safe_list.append({"match": match, "iso_date": iso_date, "time": tm, "context": ctx})
                st.session_state.deadlines = safe_list

    dl = st.session_state.deadlines
    if dl is not None:
        if len(dl) == 0:
            st.info("No deadlines found.")
        else:
            st.subheader("Found deadlines")
            for i, d in enumerate(dl, start=1):
                line = f"**{i}.** {d['match']} — **{d['iso_date']}**"
                if d.get("time"): line += f" at **{d['time']}**"
                ctx = d.get("context", "")
                st.markdown(
                    f'<div class="card">{line}<br><span class="small-muted">{ctx}</span></div>',
                    unsafe_allow_html=True
                )

            if speak_btn:
                speak_txt = "; ".join(
                    f"Deadline {i}: {d.get('match','')} on {d.get('iso_date','')}" +
                    (f" at {d.get('time')}" if d.get('time') else "")
                    for i, d in enumerate(dl, start=1)
                ) or "No deadlines found"
                mp3 = tts_say(speak_txt, "deadlines")
                if mp3: st.audio(mp3)


# ---------------- Dispatcher ----------------
if choice == "Home":
    render_home()
elif choice == "Summarize":
    render_summarize()
elif choice == "Quiz":
    render_quiz()
elif choice == "Flashcards":
    render_flashcards()
elif choice == "Deadlines":
    render_deadlines()
