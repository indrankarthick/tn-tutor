import base64
import json
import math
import os
import random
import time
import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-3.8-flash"
DOUBTS_ON = True          # set to False to hide the AI doubt tutor
DOUBT_LIMIT = 10
LADDU_EVERY = 5
TIMES = {10: 5, 25: 10, 100: 60}  # questions: minutes

# slug: (name shown, speaking style). Pictures are in the "buddies" folder.
BUDDIES = {
    "lion": ("Lion cub", "brave and encouraging"),
    "peacock": ("Peacock", "clever and calm"),
    "monkey": ("Monkey", "funny and playful"),
    "owl": ("Owl", "wise and patient"),
    "elephant": ("Elephant", "gentle and kind"),
}

GOALS = {
    "School exams": "Great practice! Every answer builds your marks.",
    "NEET": "Good effort! You are getting closer to your doctor dream.",
    "UPSC": "Good effort! You are getting closer to your IAS or IPS dream.",
    "TNPSC": "Good effort! You are getting closer to your VAO or Group exam dream.",
}

st.set_page_config(page_title="TN Tutor", page_icon="📚")
st.markdown("<style>.stApp{background:#EAF4FF}</style>", unsafe_allow_html=True)


def pic(slug, pose="read"):
    """Return the picture path for a buddy pose, or None if the file is missing."""
    suffix = "" if pose == "read" else f"_{pose}"
    path = os.path.join("buddies", f"{slug}{suffix}.webp")
    return path if os.path.exists(path) else None


def show(slug, pose="read", width=170):
    p = pic(slug, pose)
    if p:
        st.image(p, width=width)


@st.cache_resource
def bg_uri():
    p = os.path.join("buddies", "bg.webp")
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return "data:image/webp;base64," + base64.b64encode(f.read()).decode()


QUESTION_FILES = ["questions_tn12.json", "questions.json", "questions_india.json",
                  "questions_cbse12.json", "questions_cbse12_languages.json",
                  "questions_cbse12_arts.json"]


@st.cache_data
def load_bank():
    bank = {}
    for fname in QUESTION_FILES:
        if os.path.exists(fname):
            with open(fname, encoding="utf-8") as f:
                bank.update(json.load(f))
    return bank


BANK = load_bank()

defaults = {"i": 0, "answers": {}, "done": False, "started": False,
            "deadline": None, "doubts": 0, "rid": 0}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

uri = bg_uri()
if uri and not st.session_state.started:
    st.markdown(
        f'<div style="height:210px;border-radius:0 0 28px 28px;'
        f'background:#D6ECFF url({uri}) 0 0/100% auto no-repeat;'
        f'background-blend-mode:multiply"></div>', unsafe_allow_html=True)

st.title("TN Tutor")

slug = st.selectbox("Choose your buddy", list(BUDDIES),
                    format_func=lambda s: BUDDIES[s][0])
style = BUDDIES[slug][1]
name = st.text_input("Give your buddy a name", value=BUDDIES[slug][0])
buddy = name
if not st.session_state.started:
    show(slug, "read", 200)
goal = st.selectbox("My goal", list(GOALS))
chapter = st.selectbox("Choose chapter", list(BANK))
size = st.selectbox("Quiz length", list(TIMES),
                    format_func=lambda n: f"{n} questions - {TIMES[n]} min")


def new_round():
    """Prepare a new test. The timer does NOT start until Start is pressed."""
    pool = BANK[chapter]
    n = min(size, len(pool))
    # Prefer one question per concept, so a test does not repeat the same idea
    first, rest, seen = [], [], set()
    for q in random.sample(pool, len(pool)):
        cid = q.get("cid")
        if cid and cid in seen:
            rest.append(q)
        else:
            if cid:
                seen.add(cid)
            first.append(q)
    st.session_state.round = (first + rest)[:n]
    st.session_state.minutes = max(1, math.ceil(TIMES[size] * n / size))
    st.session_state.deadline = None
    st.session_state.started = False
    st.session_state.i = 0
    st.session_state.answers = {}
    st.session_state.done = False
    st.session_state.rid += 1


if st.session_state.get("cfg") != (chapter, size):
    st.session_state.cfg = (chapter, size)
    new_round()
QUESTIONS = st.session_state.round


@st.fragment(run_every=1)
def clock():
    left = int(st.session_state.deadline - time.time())
    if left <= 0:
        st.session_state.done = True
        st.rerun()
    st.markdown(f"⏱️ **Time left: {left // 60:02d}:{left % 60:02d}**")


tab1, tab2 = st.tabs(["Quiz", "Ask a doubt"])

with tab1:
    total = len(QUESTIONS)

    if not st.session_state.started:
        st.subheader("Ready to start?")
        st.write(f"📚 {chapter}")
        st.write(f"📝 {total} questions | ⏱️ {st.session_state.minutes} minutes")
        st.info("The timer starts only when you press Start test.")
        if st.button("Start test"):
            st.session_state.deadline = time.time() + st.session_state.minutes * 60
            st.session_state.started = True
            st.rerun()
    else:
        if not st.session_state.done and time.time() >= st.session_state.deadline:
            st.session_state.done = True
            st.rerun()

        if not st.session_state.done:
            i = st.session_state.i
            q = QUESTIONS[i]
            st.caption(f"Time allowed: {st.session_state.minutes} min")
            clock()
            st.subheader(f"Question {i + 1} of {total}")
            st.markdown(q["q"])
            choice = st.radio("Choose one:", q["options"], index=None,
                              key=f"r{st.session_state.rid}-q{i}",
                              label_visibility="collapsed")
            if choice is not None:
                st.session_state.answers[i] = choice
            last = i == total - 1
            c1, c2 = st.columns(2)
            with c1:
                if i > 0 and st.button("Previous"):
                    st.session_state.i -= 1
                    st.rerun()
            with c2:
                if st.button("Submit test" if last else "Next question"):
                    if last:
                        st.session_state.done = True
                    else:
                        st.session_state.i += 1
                    st.rerun()
            if not last and st.button("Finish test now"):
                st.session_state.done = True
                st.rerun()
        else:
            answers = st.session_state.answers
            correct = sum(1 for k, q in enumerate(QUESTIONS)
                          if answers.get(k) == q["options"][q["answer"]])
            attempted = len(answers)
            if time.time() >= st.session_state.deadline:
                st.warning("Time is over. Your test was submitted.")
            st.subheader(f"Score: {correct} / {total}")
            eaten = correct // LADDU_EVERY

            # Pick the buddy's mood: cheer, laddu, or gentle "try again"
            if correct == total:
                pose = "cheer"
            elif eaten >= 1:
                pose = "laddu"
            else:
                pose = "retry"
            c1, c2 = st.columns([1, 1])
            with c1:
                show(slug, pose, 220)
            with c2:
                st.write(f"Attempted: {attempted}")
                st.write(f"Wrong: {attempted - correct}")
                st.write(f"Not attempted: {total - attempted}")
                st.write(f"{buddy} ate: " + "🟡" * eaten + f" ({eaten} laddu)")
            if correct == total:
                st.success(f"Perfect! {buddy} shares a laddu 🟡 with you!")
            elif eaten >= 1:
                st.write(GOALS[goal])
            else:
                st.info("Good try! Press New test and try again. You can do it!")
            with st.expander("Review all questions and answers"):
                for k, q in enumerate(QUESTIONS):
                    right = q["options"][q["answer"]]
                    mine = answers.get(k)
                    mark = "⚪" if mine is None else ("✅" if mine == right else "❌")
                    st.markdown(f"**{mark} Question {k + 1}**")
                    st.markdown(q["q"])
                    st.markdown(f"Your answer: {mine or 'Not attempted'}")
                    st.markdown(f"**Correct answer:** {right}")
                    st.caption(q["why"])
                    st.divider()
            if st.button("New test"):
                new_round()
                st.rerun()

with tab2:
    if not DOUBTS_ON:
        st.info("The doubt tutor is coming soon. Enjoy the quiz for now!")
    else:
        left = DOUBT_LIMIT - st.session_state.doubts
        st.write(f"Doubts left in this session: {left}")
        question = st.text_input("Ask your doubt:")
        if question and left > 0:
            waiting = st.empty()
            p = pic(slug, "think")
            if p:
                waiting.image(p, width=170)
            client = genai.Client(
                api_key=os.environ["GEMINI_API_KEY"],
                http_options=types.HttpOptions(timeout=30000),
            )
            try:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=(f"You are {name}, a {style} teacher for Tamil "
                              "Nadu Class 12 students. Explain step by step "
                              "in simple language, in under 150 words. Start "
                              "directly with the answer, with no long "
                              "greeting. Answer only school-subject "
                              "questions; for anything else, politely say "
                              "you can only help with studies. " + question),
                    config=types.GenerateContentConfig(max_output_tokens=1000),
                )
                st.session_state.doubts += 1
                waiting.empty()
                st.write(response.text)
            except Exception as e:
                waiting.empty()
                st.warning("The tutor is busy right now. Please try again later.")
                st.caption(str(e)[:300])
        elif question:
            st.warning("Doubt limit reached for this session.")
