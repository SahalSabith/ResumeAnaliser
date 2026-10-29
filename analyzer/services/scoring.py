"""Local (offline) resume analysis: parsing, scoring, JD matching, suggestions, job recommendations."""
import re
from collections import Counter
from datetime import date

from . import skills_data as sd

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{8,}\d")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
RANGE_RE = re.compile(r"\b((?:19|20)\d{2})\s*(?:-|–|—|to)\s*((?:19|20)\d{2}|present|current|now|till date)", re.I)
METRIC_RE = re.compile(
    r"(?:[$₹€£]\s?\d[\d,.]*\s?[kmb]?)|(?:\d+(?:\.\d+)?\s?(?:%|x\b|k\b|\+|percent|users|customers|clients|million|lakh|crore|hours|days|members|people|projects))",
    re.I)
BULLET_RE = re.compile(r"^\s*[-•*▪●◦➢✓]\s+", re.M)

SECTION_HEADERS = {
    "summary": {"summary", "professional summary", "objective", "career objective", "profile", "about me"},
    "experience": {"experience", "work experience", "professional experience", "employment history", "internship",
                   "internships", "work history"},
    "education": {"education", "academic background", "academics", "qualification", "qualifications", "education qualifications"},
    "skills": {"skills", "technical skills", "core competencies", "key skills", "technologies", "skills summary"},
    "projects": {"projects", "project", "personal projects", "academic projects", "key projects"},
    "certifications": {"certifications", "certification", "certificates", "courses", "achievements", "awards",
                       "licenses", "certifications and awards"},
}
CORE_SECTIONS = ["summary", "experience", "education", "skills", "projects"]


# ------------------------------------------------------------------ helpers
def find_skills(text, soft=False):
    t = text.lower()
    if soft:
        t = t.replace("-", " ")
    table = sd.SOFT_PATTERNS if soft else sd.TECH_PATTERNS
    return [canon for canon, rx in table if rx.search(t)]


def split_sections(text):
    sections, current = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        norm = re.sub(r"[^a-z ]", "", line.lower()).strip()
        if line and len(line) <= 45:
            hit = next((k for k, names in SECTION_HEADERS.items() if norm in names), None)
            if hit:
                current = hit
                sections.setdefault(current, [])
                continue
        if current and line:
            sections[current].append(line)
    return sections


def _years_of_experience(text, exp_lines):
    explicit = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\b", text.lower())]
    if explicit:
        return min(max(explicit), 40)
    total, now = 0, date.today().year
    for a, b in RANGE_RE.findall("\n".join(exp_lines)):
        end = now if not b.isdigit() else int(b)
        total += max(0, min(end, now) - int(a))
    return min(total, 40)


def parse_resume(text):
    sections = split_sections(text)
    lower = text.lower()
    phones = [m for m in PHONE_RE.findall(text) if 10 <= len(re.sub(r"\D", "", m)) <= 13]
    exp_lines = sections.get("experience", [])

    edu_lines = [l for l in sections.get("education", []) if sd.DEGREE_RE.search(l) or sd.INSTITUTION_RE.search(l)]
    if not edu_lines:
        edu_lines = [l.strip() for l in text.splitlines() if sd.DEGREE_RE.search(l) and len(l) < 150]
    edu_all = "\n".join(sections.get("education", []) or edu_lines)

    proj_lines = [l for l in sections.get("projects", []) if 3 < len(l) <= 90 and not BULLET_RE.match(l)]
    exp_entries = [l for l in exp_lines if (YEAR_RE.search(l) or re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", l.lower()))
                   and len(l) < 140]
    words = re.findall(r"[A-Za-z']+", lower)
    verbs = sum(1 for w in words if w in sd.ACTION_VERBS)

    return {
        "contact": {
            "email": (EMAIL_RE.findall(text) or [""])[0],
            "phone": (phones or [""])[0].strip(),
            "linkedin": "linkedin.com" in lower,
            "github": "github.com" in lower,
        },
        "sections": sections,
        "tech_skills": find_skills(text),
        "soft_skills": find_skills(text, soft=True),
        "education": edu_lines[:6],
        "education_has_year": bool(YEAR_RE.search(edu_all)),
        "education_has_grade": bool(re.search(r"\b(cgpa|gpa|percentage|grade)\b|\d{2}(?:\.\d+)?\s?%", edu_all.lower())),
        "projects": proj_lines[:6],
        "experience": {"years": _years_of_experience(text, exp_lines), "entries": exp_entries[:8]},
        "certifications": sections.get("certifications", [])[:6],
        "stats": {
            "word_count": len(words),
            "bullets": len(BULLET_RE.findall(text)),
            "action_verbs": verbs,
            "metrics": len(METRIC_RE.findall(text)),
            "weak_phrases": sorted({p for p in sd.WEAK_PHRASES if p in lower}),
        },
    }


# ------------------------------------------------------------------ scoring
def score_resume(p):
    c, s = p["contact"], p["stats"]

    skills = round(min(len(p["tech_skills"]) / 10, 1) * 75 + min(len(p["soft_skills"]) / 3, 1) * 25)

    edu = 0
    if p["education"]:
        edu += 60
    if "education" in p["sections"]:
        edu += 20
    if p["education_has_year"] or p["education_has_grade"]:
        edu += 20

    fmt = (20 if c["email"] else 0) + (15 if c["phone"] else 0) + (10 if (c["linkedin"] or c["github"]) else 0)
    fmt += 7 * sum(1 for k in CORE_SECTIONS if k in p["sections"])
    wc = s["word_count"]
    fmt += 20 if 350 <= wc <= 1000 else 10 if (150 <= wc < 350 or 1000 < wc <= 1500) else 0

    kw = min(s["action_verbs"] / 8, 1) * 40 + min(s["metrics"] / 4, 1) * 35 + min(s["bullets"] / 8, 1) * 25
    kw -= min(len(s["weak_phrases"]) * 5, 15)
    kw = round(max(0, min(100, kw)))

    clamp = lambda v: max(0, min(100, int(v)))
    skills, edu, fmt = clamp(skills), clamp(edu), clamp(fmt)
    overall = round(0.30 * skills + 0.15 * edu + 0.25 * fmt + 0.30 * kw)
    return {"overall": overall, "skills": skills, "education": edu, "format": fmt, "keywords": kw}


# ------------------------------------------------------------------ job description matching
def top_keywords(jd, exclude=(), n=25):
    tokens = re.findall(r"[a-z][a-z+#.\-]{2,}", jd.lower())
    tokens = [t.strip(".-") for t in tokens]
    counts = Counter(t for t in tokens if len(t) > 3 and t not in sd.STOPWORDS and t not in sd.GENERIC_JD_WORDS
                     and t not in exclude)
    return [w for w, _ in counts.most_common(n)]


def match_job(p, resume_text, jd):
    jd = (jd or "").strip()
    if len(jd) < 30:
        return None
    resume_skills = set(p["tech_skills"]) | set(p["soft_skills"])
    req_tech, req_soft = find_skills(jd), find_skills(jd, soft=True)
    required = req_tech + req_soft
    matched = [s for s in required if s in resume_skills]
    missing = [s for s in required if s not in resume_skills]

    known_words = {w for s in required for w in s.split()}
    kws = top_keywords(jd, exclude=known_words)
    rlow = resume_text.lower()
    kw_missing = [k for k in kws if not re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", rlow)]

    skill_pct = round(len(matched) / len(required) * 100) if required else None
    kw_pct = round((len(kws) - len(kw_missing)) / len(kws) * 100) if kws else None
    if skill_pct is not None and kw_pct is not None:
        score = round(0.7 * skill_pct + 0.3 * kw_pct)
    else:
        score = skill_pct if skill_pct is not None else (kw_pct or 0)

    jd_years = [int(y) for y in re.findall(r"(\d+)\+?\s*(?:years|yrs)", jd.lower())]
    return {
        "score": score, "skill_pct": skill_pct, "keyword_pct": kw_pct,
        "matched": matched, "missing_skills": missing, "missing_keywords": kw_missing[:12],
        "jd_years": max(jd_years) if jd_years else None,
    }


# ------------------------------------------------------------------ suggestions & job recommendations
def build_suggestions(p, scores, match):
    out = []
    add = lambda pri, title, detail: out.append({"priority": pri, "title": title, "detail": detail, "source": "rules"})
    c, s = p["contact"], p["stats"]

    if not c["email"] or not c["phone"]:
        add("high", "Add complete contact details", "Include a professional email and a phone number at the top of the resume so recruiters can reach you.")
    if not (c["linkedin"] or c["github"]):
        add("low", "Link your professional profiles", "Add LinkedIn and, for technical roles, a GitHub link. Recruiters check them.")
    for sec, pri, msg in [
        ("skills", "high", "Add a dedicated Skills section. Applicant tracking systems (ATS) scan it first."),
        ("experience", "high", "Add an Experience or Internships section, even small projects or freelance work count."),
        ("education", "high", "Add an Education section with degree, institution and year."),
        ("projects", "medium", "Add 2-3 projects with the tech used and the result. They prove your skills."),
        ("summary", "medium", "Open with a 2-3 line summary naming your target role and strongest skills."),
    ]:
        if sec not in p["sections"]:
            add(pri, f"Missing section: {sec.title()}", msg)
    if len(p["tech_skills"]) < 6:
        add("high", "List more technical skills", f"Only {len(p['tech_skills'])} technical skills were detected. Add the tools, languages and frameworks you actually use.")
    if len(p["soft_skills"]) < 2:
        add("low", "Show soft skills through results", "Instead of listing adjectives, show leadership or teamwork inside bullet points.")
    if s["metrics"] < 3:
        add("high", "Quantify your achievements", "Add numbers: 'Reduced page load time by 35%' beats 'Improved performance'. Aim for at least 4 measurable results.")
    if s["action_verbs"] < 6:
        add("medium", "Start bullets with strong action verbs", "Use verbs like Built, Designed, Optimized, Led, Automated, Delivered.")
    if s["weak_phrases"]:
        add("medium", "Replace weak phrases", "Rewrite: " + ", ".join(f"'{w}'" for w in s["weak_phrases"]) + " with direct verbs describing what you did.")
    if s["bullets"] < 5:
        add("medium", "Use bullet points", "Short bullet points are easier to scan than paragraphs. Keep each to 1-2 lines.")
    if s["word_count"] < 300:
        add("high", "Resume is too short", f"Only {s['word_count']} words found. Aim for 400-800 words with specific achievements.")
    elif s["word_count"] > 1000:
        add("medium", "Resume is too long", "Trim to one page (two for 8+ years of experience). Remove older or irrelevant items.")
    if not p["certifications"]:
        add("low", "Add certifications or courses", "Relevant certificates (Coursera, Google, AWS, etc.) strengthen entry-level resumes.")

    if match:
        if match["missing_skills"]:
            add("high", "Add the missing job skills you really have",
                "The job asks for: " + ", ".join(match["missing_skills"][:8]) + ". Add those you have used, in Skills and in bullet points. For the rest, consider learning or a small project.")
        if match["missing_keywords"]:
            add("medium", "Mirror the job's keywords", "Naturally include terms such as: " + ", ".join(match["missing_keywords"][:8]) + ".")
        if match["jd_years"] and p["experience"]["years"] < match["jd_years"]:
            add("medium", "Experience gap", f"The job asks for {match['jd_years']}+ years; your resume shows about {p['experience']['years']:g}. Highlight internships, freelance and project work to bridge it.")
        if match["score"] < 50:
            add("high", "Tailor this resume to the job", "Match is below 50%. Reorder skills so the job's requirements come first and rewrite your summary for this role.")
    if not any(x["priority"] == "high" for x in out):
        add("low", "Strong foundation", "No critical issues found. Focus on tailoring to each job and adding more measurable results.")
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda x: order[x["priority"]])


def recommend_jobs(p, limit=5):
    have = set(p["tech_skills"])
    jobs = []
    for role, req in sd.ROLES.items():
        hit = [s for s in req if s in have]
        if hit:
            jobs.append({"role": role, "pct": round(len(hit) / len(req) * 100), "matched": hit,
                         "missing": [s for s in req if s not in have][:4]})
    jobs.sort(key=lambda j: j["pct"], reverse=True)
    return jobs[:limit]


# ------------------------------------------------------------------ public entry point
def analyze(text, jd=""):
    p = parse_resume(text)
    scores = score_resume(p)
    match = match_job(p, text, jd)
    present = [k for k in sd_order() if k in p["sections"]]
    return {
        "scores": scores,
        "parsed": {
            "contact": p["contact"], "tech_skills": p["tech_skills"], "soft_skills": p["soft_skills"],
            "education": p["education"], "projects": p["projects"], "experience": p["experience"],
            "certifications": p["certifications"], "stats": p["stats"],
            "sections_found": present,
            "sections_missing": [k for k in CORE_SECTIONS if k not in p["sections"]],
        },
        "match": match,
        "suggestions": build_suggestions(p, scores, match),
        "jobs": recommend_jobs(p),
    }


def sd_order():
    return CORE_SECTIONS + ["certifications"]
