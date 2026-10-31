import base64
import glob
import json
import math
import os
import random
import time
import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-3.8-flash"
DOUBTS_ON = False         # False = hide the AI doubt tutor (set True later)
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
STREAMS = {
    "Pure Science": "questions_science.json",
    "Computer Science": "questions_computer.json",
    "Accounts & Commerce": "questions_commerce.json",
    "Humanities": "questions_humanities.json",
    "Engineering": "questions_engineering.json",
    "Vocational & Arts": "questions_vocational.json",
    "Languages": "questions_languages.json",
}

st.set_page_config(page_title="TN Tutor", page_icon="📚")
# Light colours with dark text everywhere, so nothing turns white-on-white
st.markdown("""<style>
.stApp{background:#EAF4FF}
.block-container{max-width:720px;padding-top:1rem}
.stApp h1,.stApp h2,.stApp h3,.stApp p,.stApp li,.stApp label,.stApp span,
.stApp [data-testid="stMarkdownContainer"] *,.stApp [data-testid="stCaptionContainer"] *{color:#14213D}
.stApp .stButton>button{background:#fff;color:#14213D;border:1.5px solid #14213D;border-radius:14px;font-weight:700;min-height:48px}
.stApp .stButton>button p{color:#14213D}
.stApp .stButton>button[kind="primary"],.stApp .stButton>button[data-testid="stBaseButton-primary"]{background:#F59E0B;border:0}
.stApp input,.stApp textarea{background:#fff !important;color:#14213D !important}
.stApp div[data-baseweb="select"]>div{background:#fff}
.stApp div[data-baseweb="select"] *{color:#14213D}
div[data-baseweb="popover"] ul{background:#fff}
div[data-baseweb="popover"] *{color:#14213D}
.stApp [data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:16px}
.stApp div[role="radiogroup"] label{background:#fff;border:1.5px solid #C9D2E6;border-radius:14px;padding:10px 14px;margin-bottom:8px;width:100%}
</style>""", unsafe_allow_html=True)

S = st.session_state
for key, val in {"screen": "home", "i": 0, "answers": {}, "deadline": None, "doubts": 0, "rid": 0,
                 "round": [], "minutes": 0, "label": "", "ad_uri": None, "ad_ready": False,
                 "prefs": {"slug": "lion", "name": "Lion cub", "goal": "School exams"}}.items():
    if key not in S:
        S[key] = val


def uri_of(path, mime):
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def asset(name):
    """Find a picture in the 'buddies' folder, or loose in the main folder."""
    for folder in ("buddies", "."):
        p = os.path.join(folder, name)
        if os.path.exists(p):
            return p
    return None


@st.cache_resource
def bg_uri():
    p = asset("bg.webp")
    return uri_of(p, "image/webp") if p else None


def pick_ad():
    """A different sponsor picture each visit to the home page (files in the 'ads' folder)."""
    files = [f for ext in ("jpg", "jpeg", "png", "webp") for f in glob.glob(os.path.join("ads", f"*.{ext}"))]
    if not files:
        return None
    f = random.choice(files)
    return uri_of(f, "image/" + ("jpeg" if f.lower().endswith(("jpg", "jpeg")) else f.rsplit(".", 1)[-1].lower()))


def pic(slug, pose="read"):
    return asset(f"{slug}{'' if pose == 'read' else '_' + pose}.webp")


def show(slug, pose="read", width=170):
    p = pic(slug, pose)
    if p:
        st.image(p, width=width)


def go(screen):
    S.screen = screen
    if screen == "home":
        S.ad_uri = pick_ad()
    st.rerun()


@st.cache_data
def load_stream(fname):
    if not os.path.exists(fname):
        return {}
    with open(fname, encoding="utf-8") as f:
        return json.load(f)


def start_test(pool, label, size):
    n = min(size, len(pool))
    first, rest, seen = [], [], set()        # prefer one question per idea
    for q in random.sample(pool, len(pool)):
        cid = q.get("cid")
        if cid and cid in seen:
            rest.append(q)
        else:
            if cid:
                seen.add(cid)
            first.append(q)
    S.round = (first + rest)[:n]
    S.minutes = max(1, math.ceil(TIMES[size] * n / size))
    S.deadline = time.time() + S.minutes * 60     # the clock starts NOW
    S.i, S.answers, S.label = 0, {}, label
    S.rid += 1
    S.screen = "quiz"
    st.rerun()


@st.fragment(run_every=1)
def clock():
    left = int(S.deadline - time.time())
    if left <= 0:
        S.screen = "result"
        st.rerun()
    st.markdown(f"⏱️ **Time left: {left // 60:02d}:{left % 60:02d}**")


# ---------------- screen 1: opening page ----------------
def screen_home():
    if not S.ad_ready:
        S.ad_uri, S.ad_ready = pick_ad(), True
    st.title("TN Tutor")
    st.caption("Learn. Quiz. Win laddus.")
    uri = bg_uri()
    ad = (f'<img src="{S.ad_uri}" style="width:100%;height:100%;object-fit:cover">'
          if S.ad_uri else "Your ad here")
    if uri:
        st.markdown(
            f'<div style="position:relative;border-radius:24px;overflow:hidden;padding-top:150%;'
            f'background:#D6ECFF url({uri}) 0 0/100% auto no-repeat;background-blend-mode:multiply">'
            f'<div style="position:absolute;left:4%;right:4%;top:78.5%;bottom:4%;border-radius:14px;'
            f'background:rgba(255,255,255,.92);display:flex;align-items:center;justify-content:center;'
            f'overflow:hidden;color:#4A5675;font-weight:700;font-size:13px">{ad}</div></div>',
            unsafe_allow_html=True)
    if st.button("Let’s start", type="primary", use_container_width=True):
        go("setup")


# ---------------- screen 2: choose options ----------------
def screen_setup():
    uri = bg_uri()
    if uri:
        st.markdown(f'<div style="height:170px;border-radius:24px;background:#D6ECFF url({uri}) 0 0/100% auto '
                    f'no-repeat;background-blend-mode:multiply"></div>', unsafe_allow_html=True)
    st.header("Set up your test")
    slug = st.selectbox("Choose your buddy", list(BUDDIES), format_func=lambda s: BUDDIES[s][0])
    show(slug, "read", 170)
    name = st.text_input("Give your buddy a name", value=BUDDIES[slug][0], key=f"name-{slug}")
    goal = st.selectbox("My goal", list(GOALS))
    S.prefs = {"slug": slug, "name": name, "goal": goal}

    stream = st.selectbox("Choose group", list(STREAMS))
    bank = load_stream(STREAMS[stream])
    subjects = {}
    for key in bank:
        parts = key.split(" - ", 2)
        subjects.setdefault(" - ".join(parts[:2]), {})[parts[2] if len(parts) > 2 else "Whole subject"] = key
    if not subjects:
        st.warning("This group is not available yet.")
        return
    subject = st.selectbox("Choose subject", list(subjects))
    chapters = subjects[subject]
    chap = st.selectbox("Choose chapter", (["All chapters"] + list(chapters)) if len(chapters) > 1 else list(chapters))
    keys = list(chapters.values()) if chap == "All chapters" else [chapters[chap]]
    pool = [q for k in keys for q in bank[k]]
    label = subject if chap == "Whole subject" else f"{subject} · {chap}"
    size = st.selectbox("Quiz length", list(TIMES), format_func=lambda n: f"{n} questions - {TIMES[n]} min")

    n = min(size, len(pool))
    with st.container(border=True):
        st.markdown(f"**{label}**")
        st.write(f"📝 {n} questions  |  ⏱️ {max(1, math.ceil(TIMES[size] * n / size))} minutes")
        st.caption("The timer starts only when you press Start test.")
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Back"):
            go("home")
    with c2:
        if st.button("Start test", type="primary", use_container_width=True):
            start_test(pool, label, size)


# ---------------- screen 3: the quiz ----------------
def screen_quiz():
    if time.time() >= S.deadline:
        go("result")
    total = len(S.round)
    i = S.i
    q = S.round[i]
    st.caption(f"{S.label}  ·  time allowed: {S.minutes} min")
    clock()
    st.progress((i + 1) / total)
    st.subheader(f"Question {i + 1} of {total}")
    with st.container(border=True):
        st.markdown(q["q"])
    choice = st.radio("Choose one:", q["options"], index=None,
                      key=f"r{S.rid}-q{i}", label_visibility="collapsed")
    if choice is not None:
        S.answers[i] = choice
    last = i == total - 1
    c1, c2 = st.columns(2)
    with c1:
        if i > 0 and st.button("Previous", use_container_width=True):
            S.i -= 1
            st.rerun()
    with c2:
        if st.button("Submit test" if last else "Next question", type="primary", use_container_width=True):
            if last:
                go("result")
            S.i += 1
            st.rerun()
    if not last and st.button("Finish test now"):
        go("result")


# ---------------- screen 4: result ----------------
def screen_result():
    p = S.prefs
    buddy = p["name"]
    answers = S.answers
    total = len(S.round)
    correct = sum(1 for k, q in enumerate(S.round) if answers.get(k) == q["options"][q["answer"]])
    attempted = len(answers)
    if S.deadline and time.time() >= S.deadline:
        st.warning("Time is over. Your test was submitted.")
    st.subheader(f"Score: {correct} / {total}")
    eaten = correct // LADDU_EVERY
    pose = "cheer" if correct == total else ("laddu" if eaten >= 1 else "retry")
    c1, c2 = st.columns(2)
    with c1:
        show(p["slug"], pose, 220)
    with c2:
        st.write(f"Attempted: {attempted}")
        st.write(f"Wrong: {attempted - correct}")
        st.write(f"Not attempted: {total - attempted}")
        st.write(f"{buddy} ate: " + "🟡" * eaten + f" ({eaten} laddu)")
    if correct == total:
        st.success(f"Perfect! {buddy} shares a laddu 🟡 with you!")
    elif eaten >= 1:
        st.write(GOALS[p["goal"]])
    else:
        st.info("Good try! Press New test and try again. You can do it!")
    with st.expander("Review all questions and answers"):
        for k, q in enumerate(S.round):
            right = q["options"][q["answer"]]
            mine = answers.get(k)
            mark = "⚪" if mine is None else ("✅" if mine == right else "❌")
            st.markdown(f"**{mark} Question {k + 1}**")
            st.markdown(q["q"])
            st.markdown(f"Your answer: {mine or 'Not attempted'}")
            st.markdown(f"**Correct answer:** {right}")
            st.caption(q["why"])
            st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("New test", type="primary", use_container_width=True):
            go("setup")
    with c2:
        if st.button("Home", use_container_width=True):
            go("home")


# ---------------- ask a doubt ----------------
def screen_doubt():
    p = S.prefs
    if not DOUBTS_ON:
        st.info("The doubt tutor is coming soon. Enjoy the quiz for now!")
        return
    left = DOUBT_LIMIT - S.doubts
    st.write(f"Doubts left in this session: {left}")
    question = st.text_input("Ask your doubt:")
    if question and left > 0:
        waiting = st.empty()
        t = pic(p["slug"], "think")
        if t:
            waiting.image(t, width=170)
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                              http_options=types.HttpOptions(timeout=30000))
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=(f"You are {p['name']}, a {BUDDIES[p['slug']][1]} teacher for Tamil "
                          "Nadu Class 12 students. Explain step by step in simple language, in "
                          "under 150 words. Start directly with the answer, with no long "
                          "greeting. Answer only school-subject questions; for anything else, "
                          "politely say you can only help with studies. " + question),
                config=types.GenerateContentConfig(max_output_tokens=1000))
            S.doubts += 1
            waiting.empty()
            st.write(response.text)
        except Exception as e:
            waiting.empty()
            st.warning("The tutor is busy right now. Please try again later.")
            st.caption(str(e)[:300])
    elif question:
        st.warning("Doubt limit reached for this session.")


# ---------------- which screen to show ----------------
if S.screen == "quiz":                  # the quiz has the whole page, no other tabs
    screen_quiz()
else:
    t_test, t_doubt = st.tabs(["Test", "Ask a doubt"])
    with t_test:
        {"home": screen_home, "setup": screen_setup, "result": screen_result}[S.screen]()
    with t_doubt:
        screen_doubt()
