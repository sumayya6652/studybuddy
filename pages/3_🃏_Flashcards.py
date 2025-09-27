import streamlit as st, re
from ui_utils import load_css, uploader_block
from nlp_tasks import make_flashcards

st.set_page_config(page_title="Flashcards", page_icon="🃏", layout="wide")
load_css()
st.title("🃏 Flashcards")

with st.sidebar:
    st.header("Flashcard Settings")
    num_cards = st.slider("Number of cards", 3, 20, 8, 1)

text, source = uploader_block("📂 Upload / paste text for flashcards")

if "flashcards" not in st.session_state:
    st.session_state.flashcards = None
    st.session_state.idx = 0
    st.session_state.flipped = False

colA, colB = st.columns([1,1])
with colA:
    gen = st.button("🃏 Generate Flashcards", type="primary")
with colB:
    reset = st.button("🔄 Reset")

if reset:
    st.session_state.flashcards = None
    st.session_state.idx = 0
    st.session_state.flipped = False

if gen:
    if not text.strip():
        st.warning("Upload or paste text first.")
    else:
        cards = make_flashcards(re.sub(r"\s+"," ", text), num_cards=int(num_cards))
        if not cards:
            st.error("Could not generate flashcards. Try more/longer text.")
        else:
            st.session_state.flashcards = cards
            st.session_state.idx = 0
            st.session_state.flipped = False

# Render flip-card
if st.session_state.flashcards:
    q, a = st.session_state.flashcards[st.session_state.idx]
    st.subheader(f"Card {st.session_state.idx+1}/{len(st.session_state.flashcards)}")
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

    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        if st.button("⬅️ Prev"):
            if st.session_state.idx > 0:
                st.session_state.idx -= 1
                st.session_state.flipped = False
    with c2:
        if st.button("🔄 Flip"):
            st.session_state.flipped = not st.session_state.flipped
    with c3:
        if st.button("➡️ Next"):
            if st.session_state.idx < len(st.session_state.flashcards)-1:
                st.session_state.idx += 1
                st.session_state.flipped = False
