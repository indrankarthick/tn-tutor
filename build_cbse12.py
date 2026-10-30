"""Convert the quiz-bank JSON/Excel files into the tutor app format, one file per GROUP.
Usage:  python build_cbse12.py <folder with the *_500_QA.json / *_500_MCQs.xlsx files>
Writes: questions_science.json, questions_computer.json, questions_commerce.json,
        questions_humanities.json, questions_engineering.json, questions_vocational.json,
        questions_languages.json   (Tamil Nadu subjects are listed first inside each file)
If a questions.json (English Core) is in the current folder, it is added to Languages.
"""
import glob, hashlib, json, os, random, re, sys

src = sys.argv[1] if len(sys.argv) > 1 else "."
# keep symbols (+, -, =) so maths questions that differ only by a sign stay different
norm = lambda s: re.sub(r"\s+", " ", str(s).lower()).strip()
NAME = re.compile(r"^(CBSE_Class_12|Tamil_Nadu_Class_12|Class_12|Hindustani)_(.+?)_500_(?:QA|MCQs)")
LABEL = {"CBSE_Class_12": "CBSE 12", "Tamil_Nadu_Class_12": "TN 12", "Class_12": "Class 12", "Hindustani": "Hindustani"}

GROUPS = {   # which file each subject goes to
    "science": {"Physics", "Chemistry", "Mathematics", "Biology", "Botany", "Zoology", "Biotechnology"},
    "computer": {"Computer_Science", "Informatics_Practices"},
    "commerce": {"Accountancy", "Business_Studies", "Economics", "Commerce", "Business_Mathematics",
                 "Applied_Mathematics", "Entrepreneurship"},
    "humanities": {"History", "Geography", "Civics_Political_Science", "Sociology", "Psychology", "Legal_Studies",
                   "General_Studies", "Knowledge_Traditions_Practices_India"},
    "engineering": {"Engineering_Graphics"},
    "vocational": {"Work_Experience", "NCC", "Physical_Education", "Health_and_Physical_Wellbeing", "Home_Science",
                   "Fine_Arts", "Dance", "Carnatic_Melodic", "Carnatic_Vocal", "Carnatic_Percussion",
                   "Melodic", "Vocal", "Percussion"},
    "languages": {"Arabic", "Assamese", "Bengali", "Bhoti", "Bhutia", "Bodo", "French", "German", "Gujarati",
                  "Hindi", "Hindi_Elective", "English_Elective", "Lepcha", "Nepali", "Odia", "Punjabi", "Tamil",
                  "Tamil_Practice", "Telugu_AP", "Telugu_Telangana", "Urdu_Core", "Urdu_Elective", "Malayalam",
                  "Kannada", "Marathi", "Mizo", "Manipuri", "Kashmiri", "Japanese", "Persian", "Sanskrit_Core",
                  "Sanskrit_Elective", "Limboo", "Russian", "Sindhi", "Tangkhul", "Tibetan", "Spanish"},
}
GROUP_OF = {n: g for g, names in GROUPS.items() for n in names}

def items(d):
    if isinstance(d, list):
        for q in d: yield "", q
    elif "questions" in d:
        for q in d["questions"]: yield "", q
    else:                                   # already chapter-wise
        for k, v in d.items():
            for q in v: yield " - " + k.split(" - ", 1)[-1], q

def xlsx_items(path):
    import pandas as pd
    df = pd.read_excel(path, sheet_name=0, dtype=str).fillna("")
    for r in df.to_dict("records"):
        o = [r["Option_A"], r["Option_B"], r["Option_C"], r["Option_D"]]
        yield " - " + r.get("Unit", "").strip(), {
            "id": r["Question_ID"], "topic": r.get("Chapter_or_Topic", ""), "difficulty": r.get("Difficulty", ""),
            "question": r["Question"], "options": o,
            "answer_index": "ABCD".index(r["Correct_Option"].strip().upper()), "explanation": r.get("Explanation", "")}

def clean(q, pre):
    o = q.get("options")
    if not o: return None
    if isinstance(o[0], dict): o = [x["text"] for x in o]
    text = q.get("question") or q.get("q")
    a = q.get("correct_answer", q.get("answer"))
    if isinstance(q.get("answer_index"), int): ai = q["answer_index"]
    elif a in o: ai = o.index(a)
    elif isinstance(a, str) and len(a.strip()) == 1 and a.strip().upper() in "ABCD": ai = "ABCD".index(a.strip().upper())
    elif isinstance(a, int): ai = a
    else: return None
    if len(o) != 4 or not text or len({norm(x) for x in o}) < 4 or not 0 <= ai < 4: return None
    right = o[ai]; qid = str(q.get("id", ""))
    o = o[:]; random.Random(pre + qid + text).shuffle(o)             # stop "always A"
    return {"id": f"{pre}{qid}", "topic": q.get("topic", ""), "level": q.get("difficulty") or q.get("level", ""),
            "q": text.strip(), "options": o, "answer": o.index(right),
            "why": (q.get("explanation") or q.get("why") or "").strip(),
            "cid": q.get("concept_id"), "reviewed": False}

outs = {g: {} for g in GROUPS}
seen_files, report, used_ids, seen_q = {}, [], set(), {}
files = sorted(glob.glob(os.path.join(src, "*.json")) + glob.glob(os.path.join(src, "*.xlsx")))
for f in files:
    m = NAME.match(os.path.basename(f))
    if not m: continue
    board, name = m.group(1), m.group(2)
    raw = open(f, "rb").read(); h = hashlib.md5(raw).hexdigest()
    if h in seen_files:
        report.append(f"SKIPPED duplicate file {os.path.basename(f)} (same as {seen_files[h]})"); continue
    seen_files[h] = os.path.basename(f)
    if name not in GROUP_OF:
        report.append(f"WARNING: {name} is not in any group, put in humanities"); GROUP_OF[name] = "humanities"
    g = GROUP_OF[name]
    pre = f"{LABEL[board]}-{name}-".upper().replace(" ", "")
    kept = dropped = 0; keys = seen_q.setdefault((g, board, name), set())   # same subject in 2 files: no repeats
    for suf, q in (xlsx_items(f) if f.endswith(".xlsx") else items(json.loads(raw))):
        c = clean(q, pre)
        k = (suf, norm(q.get("question") or q.get("q") or ""))
        if c is None or k in keys: dropped += 1; continue
        keys.add(k); kept += 1
        if c["id"] == pre or c["id"] in used_ids:                       # missing or repeated id
            base, n = f"{pre}{kept:04d}", 2
            c["id"] = base
            while c["id"] in used_ids: c["id"] = f"{base}-{n}"; n += 1
        used_ids.add(c["id"])
        outs[g].setdefault(f"{LABEL[board]} - {name.replace('_', ' ')}{suf}", []).append(c)
    report.append(f"{LABEL[board]} {name} -> {g}: kept {kept}, dropped {dropped}")

if os.path.exists("questions.json"):          # the 500 English Core questions
    for k, v in json.load(open("questions.json", encoding="utf-8")).items():
        outs["languages"]["CBSE 12 - " + k] = v

for g, data in outs.items():
    ordered = dict(sorted(data.items(), key=lambda kv: (not kv[0].startswith("TN 12"),)))   # Tamil Nadu first
    json.dump(ordered, open(f"questions_{g}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"questions_{g}.json", sum(len(v) for v in ordered.values()), "questions in", len(ordered), "groups")
print("\n".join(report))
