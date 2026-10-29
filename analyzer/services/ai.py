"""Free AI layer using Google Gemini's free tier, with a local fallback.

Privacy: text is sanitized (email, phone, URLs removed) before leaving the server, and AI is only
called when the user explicitly ticks the "Use AI" box. With no GEMINI_API_KEY everything runs locally.
"""
import json
import logging
import re
import urllib.request

from django.conf import settings

log = logging.getLogger(__name__)


def ai_enabled():
    return bool(settings.GEMINI_API_KEY)


def sanitize(text, limit=6000):
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    text = re.sub(r"https?://\S+|www\.\S+|linkedin\.com\S*|github\.com\S*", "[link]", text)
    text = re.sub(r"\+?\d[\d\s\-()]{8,}\d", "[phone]", text)
    return text[:limit]


def _call(prompt, json_mode=True):
    if not ai_enabled():
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    gen = {"temperature": 0.4}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = json.load(r)
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:  # network, quota, bad key... always fall back gracefully
        log.warning("Gemini call failed: %s", exc)
        return None


def _json(raw):
    if not raw:
        return None
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(raw)
    except ValueError:
        return None


# ------------------------------------------------------------------ resume review
def review_resume(text, jd=""):
    prompt = (
        "You are an expert technical recruiter and resume coach. Review the resume below"
        + (" against the job description." if jd else ".")
        + " Reply ONLY with JSON: {\"summary\": str (2-3 sentences), \"strengths\": [str, max 4], "
          "\"suggestions\": [{\"title\": str, \"detail\": str}, max 5], "
          "\"rewrites\": [{\"before\": str, \"after\": str}, max 3]}. "
          "Be specific, honest and never invent experience the candidate does not have.\n\n"
        f"RESUME:\n{sanitize(text)}\n\n" + (f"JOB DESCRIPTION:\n{sanitize(jd, 3000)}" if jd else "")
    )
    data = _json(_call(prompt))
    if not isinstance(data, dict):
        return None
    return {
        "summary": str(data.get("summary", ""))[:800],
        "strengths": [str(x)[:200] for x in data.get("strengths", [])][:4],
        "suggestions": [{"title": str(s.get("title", ""))[:100], "detail": str(s.get("detail", ""))[:400]}
                        for s in data.get("suggestions", []) if isinstance(s, dict)][:5],
        "rewrites": [{"before": str(r.get("before", ""))[:300], "after": str(r.get("after", ""))[:300]}
                     for r in data.get("rewrites", []) if isinstance(r, dict)][:3],
    }


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
            return {"rewrites": [str(x) for x in data["rewrites"]][:3], "tips": [str(x) for x in data.get("tips", [])][:2], "ai": True}
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
