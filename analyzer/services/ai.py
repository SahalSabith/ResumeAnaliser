"""Google Gemini layer used across analysis, builder, and writing tools.

Privacy: email, phone and URLs are stripped before any request leaves the server.
If the key is missing, tests are running, or Gemini is down, callers get a local fallback.
"""
import json
import logging
import re
import sys
import time
import urllib.error
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)

_working_model = None
_last_error = ""

FALLBACK_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
]


def last_error():
    return _last_error


def ai_enabled():
    if "test" in sys.argv or getattr(settings, "TESTING", False):
        return False
    return bool(settings.GEMINI_API_KEY)


def sanitize(text, limit=6000):
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text or "")
    text = re.sub(r"https?://\S+|www\.\S+|linkedin\.com\S*|github\.com\S*", "[link]", text)
    text = re.sub(r"\+?\d[\d\s\-()]{8,}\d", "[phone]", text)
    return text[:limit]


def _model_list():
    seen, out = set(), []
    preferred = [_working_model, settings.GEMINI_MODEL, *FALLBACK_MODELS]
    for name in preferred:
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _extract_text(data):
    cand = (data.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    chunks = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    return "\n".join(chunks).strip()


def _post(model, prompt, json_mode, thinking):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    gen = {"temperature": 0.4}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    if thinking:
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def _call(prompt, json_mode=True):
    global _working_model, _last_error
    if not ai_enabled():
        return None
    last = None
    for model in _model_list():
        for thinking in (True, False):
            try:
                data = _post(model, prompt, json_mode, thinking)
                text = _extract_text(data)
                if not text:
                    last = "empty Gemini response"
                    continue
                _working_model = model
                _last_error = ""
                return text
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:400]
                last = f"HTTP {exc.code} ({model}): {detail}"
                log.warning("Gemini %s failed: %s", model, last)
                if exc.code == 400 and thinking:
                    continue
                if exc.code in (404, 400):
                    break
                if exc.code == 503:
                    time.sleep(0.4)
                    if thinking:
                        continue
                    break
                return None
            except Exception as exc:
                last = f"{type(exc).__name__}: {exc}"
                log.warning("Gemini call failed: %s", last)
                return None
    _last_error = last or "Gemini unavailable"
    return None


def _json(raw):
    if not raw:
        return None
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(raw)
    except ValueError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except ValueError:
                return None
        return None


def _strs(items, n, limit=400):
    if not isinstance(items, list):
        return []
    return [str(x)[:limit] for x in items if str(x).strip()][:n]


def _dicts(items, keys, n):
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        out.append({k: str(item.get(k, ""))[:lim] for k, lim in keys})
        if len(out) >= n:
            break
    return out


# ------------------------------------------------------------------ resume review (one call covers the analysis page)
def enrich_resume(text, jd="", job_title=""):
    prompt = (
        "You are an expert technical recruiter and resume coach. Review the resume"
        + (f" for the target role '{job_title}'." if job_title else ".")
        + (" Compare it to the job description." if jd else "")
        + " Be specific, honest, and never invent experience.\n"
        "Reply ONLY with JSON: {"
        "\"summary\": str (2-3 sentences),"
        "\"strengths\": [str, max 4],"
        "\"suggestions\": [{\"title\": str, \"detail\": str}, max 5],"
        "\"rewrites\": [{\"before\": str, \"after\": str}, max 3],"
        "\"ats_keywords\": [str, max 10 missing keywords the resume should add if true],"
        "\"interview\": [{\"q\": str, \"tip\": str}, max 5 likely interview questions],"
        "\"career\": [{\"role\": str, \"why\": str, \"gap\": str}, max 4 next-step roles],"
        "\"match_notes\": str (2 sentences on JD fit, empty if no JD)"
        "}\n\n"
        f"RESUME:\n{sanitize(text)}\n\n"
        + (f"JOB DESCRIPTION:\n{sanitize(jd, 3000)}" if jd else "")
    )
    data = _json(_call(prompt))
    if not isinstance(data, dict):
        return None
    return {
        "summary": str(data.get("summary", ""))[:800],
        "strengths": _strs(data.get("strengths"), 4, 200),
        "suggestions": _dicts(data.get("suggestions"), (("title", 100), ("detail", 400)), 5),
        "rewrites": _dicts(data.get("rewrites"), (("before", 300), ("after", 300)), 3),
        "ats_keywords": _strs(data.get("ats_keywords"), 10, 40),
        "interview": _dicts(data.get("interview"), (("q", 240), ("tip", 320)), 5),
        "career": _dicts(data.get("career"), (("role", 80), ("why", 240), ("gap", 240)), 4),
        "match_notes": str(data.get("match_notes", ""))[:500],
    }


def review_resume(text, jd=""):
    pack = enrich_resume(text, jd)
    if not pack:
        return None
    return {k: pack[k] for k in ("summary", "strengths", "suggestions", "rewrites")}


# ------------------------------------------------------------------ helper tools
WEAK_MAP = [("responsible for", "Led"), ("worked on", "Developed"), ("helped with", "Supported"),
            ("helped", "Supported"), ("duties included", "Handled"), ("tasked with", "Executed"),
            ("assisted in", "Contributed to")]


def improve_bullet(text, use_ai=True):
    text = text.strip()
    if use_ai and ai_enabled():
        data = _json(_call(
            "Rewrite this resume bullet in 3 stronger versions: start with an action verb, be concise, add a "
            "placeholder like [X%] where a metric belongs, never invent facts. Reply ONLY JSON: "
            f"{{\"rewrites\": [str, str, str], \"tips\": [str, max 2]}}.\nBullet: {sanitize(text, 600)}"))
        if isinstance(data, dict) and data.get("rewrites"):
            return {"rewrites": _strs(data["rewrites"], 3, 280), "tips": _strs(data.get("tips"), 2, 220), "ai": True}
    clean = re.sub(r"^[-•*]\s*", "", text)
    low = clean.lower()
    for weak, strong in WEAK_MAP:
        if low.startswith(weak):
            clean = strong + clean[len(weak):]
            break
    clean = clean[0].upper() + clean[1:] if clean else clean
    tips = []
    if not re.search(r"\d", clean):
        tips.append("Add a number: how many users, how much faster, how much saved?")
    if len(clean.split()) > 28:
        tips.append("Shorten to one or two lines.")
    if clean == text:
        tips.append("Start with a strong action verb such as Built, Led, Optimized or Automated.")
    return {"rewrites": [clean.rstrip(".") + "."], "tips": tips, "ai": False}


def generate_summary(role, skills, years, use_ai=True):
    skills_list = [s.strip() for s in re.split(r"[,\n]", skills) if s.strip()][:8]
    if use_ai and ai_enabled():
        raw = _call(f"Write a 2-3 sentence professional resume summary (first person implied, no 'I') for a {role} "
                    f"with {years or 'entry-level'} experience skilled in {', '.join(skills_list)}. "
                    "Plain text only, no invented employers or numbers.", json_mode=False)
        if raw:
            return raw.strip().strip('"'), True
    exp = f"{years}+ years of experience" if years and str(years).strip() not in ("0", "") else "a strong learning mindset"
    top = ", ".join(skills_list[:5]) or "modern tools and technologies"
    return (f"{role} with {exp}, skilled in {top}. Focused on building reliable, well-tested solutions and "
            f"communicating clearly with teams. Looking to contribute to impactful products as a {role}."), False


def cover_letter(role, company, skills, jd, name, use_ai=True):
    skills_list = [s.strip() for s in re.split(r"[,\n]", skills) if s.strip()][:6]
    if use_ai and ai_enabled():
        raw = _call(f"Write a concise cover letter (under 220 words) from {name or 'the candidate'} applying for "
                    f"{role} at {company or 'the company'}. Skills: {', '.join(skills_list)}. "
                    f"Job description (may be empty): {sanitize(jd, 2500)}. Professional, specific, honest, no invented facts. "
                    "Plain text.", json_mode=False)
        if raw:
            return raw.strip(), True
    sk = ", ".join(skills_list) or "relevant technical skills"
    return (f"Dear Hiring Manager,\n\nI am excited to apply for the {role} position at {company or 'your company'}. "
            f"My background in {sk} has prepared me to contribute from day one, and I enjoy turning requirements "
            f"into dependable, well-structured work.\n\nIn my recent projects I focused on clear communication, "
            f"measurable results and continuous learning. I would welcome the chance to discuss how my skills match "
            f"your team's needs.\n\nThank you for your time and consideration.\n\nSincerely,\n{name or '[Your name]'}"), False


def linkedin_about(role, skills, years, use_ai=True):
    skills_list = [s.strip() for s in re.split(r"[,\n]", skills) if s.strip()][:8]
    if use_ai and ai_enabled():
        raw = _call(f"Write a LinkedIn About section (120-180 words, first person) for a {role} with "
                    f"{years or 'early'} years of experience. Skills: {', '.join(skills_list)}. Warm, concrete, no fake employers.",
                    json_mode=False)
        if raw:
            return raw.strip(), True
    top = ", ".join(skills_list[:5]) or "building useful software"
    return (f"I'm a {role} who enjoys {top}. I like turning messy problems into clear, working products and "
            f"learning in public. Open to roles where I can ship, measure, and keep improving."), False


def interview_prep(role, skills, jd="", use_ai=True):
    skills_list = [s.strip() for s in re.split(r"[,\n]", skills) if s.strip()][:8]
    if use_ai and ai_enabled():
        data = _json(_call(
            f"Create interview prep for a {role}. Skills: {', '.join(skills_list)}. "
            f"JD (optional): {sanitize(jd, 2000)}. Reply ONLY JSON: "
            "{\"questions\": [{\"q\": str, \"tip\": str}, max 6]}"))
        if isinstance(data, dict) and data.get("questions"):
            return {"questions": _dicts(data["questions"], (("q", 240), ("tip", 320)), 6), "ai": True}
    qs = [
        {"q": f"Walk me through a project that shows you can do this {role} job.",
         "tip": "Use STAR: situation, task, action, result. Name the tech and a number."},
        {"q": "Tell me about a time something broke. What did you do?",
         "tip": "Show debugging, communication, and what you changed so it would not happen again."},
        {"q": "Why this role, and why this company?",
         "tip": "Connect 2 skills you have to 2 needs in the job posting."},
    ]
    return {"questions": qs, "ai": False}


def tailor_to_job(resume_text, jd, use_ai=True):
    if use_ai and ai_enabled() and jd.strip():
        data = _json(_call(
            "Tailor this resume to the job. Never invent experience. Reply ONLY JSON: "
            "{\"summary\": str, \"keywords_to_add\": [str, max 8], \"bullet_rewrites\": [{\"before\": str, \"after\": str}, max 4], "
            "\"missing\": [str, max 6]}.\n"
            f"RESUME:\n{sanitize(resume_text, 5000)}\n\nJD:\n{sanitize(jd, 2500)}"))
        if isinstance(data, dict):
            return {
                "summary": str(data.get("summary", ""))[:600],
                "keywords_to_add": _strs(data.get("keywords_to_add"), 8, 40),
                "bullet_rewrites": _dicts(data.get("bullet_rewrites"), (("before", 280), ("after", 280)), 4),
                "missing": _strs(data.get("missing"), 6, 80),
                "ai": True,
            }
    return {"summary": "", "keywords_to_add": [], "bullet_rewrites": [],
            "missing": ["Paste a job description so AI can tailor the resume."], "ai": False}


def suggest_skills(role, existing="", use_ai=True):
    have = [s.strip() for s in re.split(r"[,\n]", existing) if s.strip()][:20]
    if use_ai and ai_enabled():
        data = _json(_call(
            f"Suggest realistic skills for a {role} resume. Candidate already lists: {', '.join(have) or 'none'}. "
            "Only common, honest skills for that role — do not invent rare certs. Reply ONLY JSON: "
            "{\"skills\": [str, max 12], \"note\": str}"))
        if isinstance(data, dict) and data.get("skills"):
            return {"skills": _strs(data["skills"], 12, 40), "note": str(data.get("note", ""))[:240], "ai": True}
    defaults = ["Python", "SQL", "Git", "REST APIs", "Problem solving", "Communication"]
    merged = list(dict.fromkeys(have + defaults))[:12]
    return {"skills": merged, "note": "Starter list — keep only skills you can discuss in an interview.", "ai": False}


def rewrite_section(section, text, role="", use_ai=True):
    text = (text or "").strip()
    if not text:
        return "", False
    if use_ai and ai_enabled():
        raw = _call(
            f"Rewrite this resume {section} for a {role or 'professional'} role. Keep the same facts, dates and employers. "
            "Use strong verbs and short bullets. Plain text only, same overall structure.\n\n"
            f"{sanitize(text, 4000)}", json_mode=False)
        if raw:
            return raw.strip(), True
    return text, False
