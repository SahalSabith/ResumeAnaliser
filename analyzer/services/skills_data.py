"""Skill dictionaries used by the local analyzer (works fully offline)."""
import re

TECH = [
    "python", "java", "javascript", "typescript", "c++", "c#", "php", "ruby", "go", "kotlin", "swift", "rust",
    "sql", "mysql", "postgresql", "mongodb", "sqlite", "redis", "html", "css", "sass", "bootstrap", "tailwind css",
    "react", "angular", "vue.js", "next.js", "node.js", "express.js", "django", "flask", "fastapi", "spring boot",
    ".net", "laravel", "rest api", "graphql", "microservices", "git", "github", "docker", "kubernetes", "aws",
    "azure", "google cloud", "terraform", "jenkins", "ci/cd", "linux", "bash", "ansible", "nginx", "pandas",
    "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "opencv", "machine learning", "deep learning",
    "natural language processing", "data analysis", "data visualization", "tableau", "power bi", "excel", "etl",
    "apache spark", "hadoop", "kafka", "airflow", "statistics", "jira", "agile", "scrum", "selenium", "pytest",
    "junit", "postman", "figma", "android", "flutter", "react native", "firebase", "oauth", "jwt",
    "cybersecurity", "penetration testing", "network security", "siem", "seo", "google analytics",
    "unit testing", "data structures", "algorithms", "oop", "system design", "llm", "prompt engineering",
    "generative ai", "computer vision", "django rest framework", "celery", "rabbitmq", "elasticsearch", "jquery",
    "wordpress", "wireframing", "prototyping", "user research", "blockchain", "api testing", "test automation", "maven", "networking",
]

TECH_ALIASES = {
    "javascript": ["js", "es6"], "typescript": ["ts"], "react": ["reactjs", "react.js"],
    "vue.js": ["vue", "vuejs"], "next.js": ["nextjs"], "node.js": ["nodejs", "node"], "express.js": ["expressjs"],
    "postgresql": ["postgres"], "kubernetes": ["k8s"], "google cloud": ["gcp"], "aws": ["amazon web services"],
    "scikit-learn": ["sklearn", "scikit learn"], "machine learning": ["ml"],
    "natural language processing": ["nlp"], "power bi": ["powerbi"], "excel": ["ms excel", "microsoft excel"],
    "rest api": ["rest apis", "restful", "restful api", "restful apis"], "go": ["golang"],
    ".net": ["dotnet", ".net core", "asp.net"], "tailwind css": ["tailwind"], "spring boot": ["springboot", "spring"],
    "ci/cd": ["cicd", "ci cd"], "generative ai": ["genai", "gen ai", "large language models"],
    "django rest framework": ["drf"], "html": ["html5"], "css": ["css3"], "data structures": ["data structure", "dsa"],
    "unit testing": ["unit tests"], "oop": ["object oriented", "object-oriented"],
}

SOFT = [
    "communication", "leadership", "teamwork", "problem solving", "time management", "adaptability",
    "critical thinking", "collaboration", "creativity", "presentation", "negotiation", "mentoring",
    "analytical thinking", "decision making", "project management", "attention to detail", "public speaking",
    "stakeholder management", "customer service",
]
SOFT_ALIASES = {
    "teamwork": ["team player", "team work", "team collaboration"],
    "analytical thinking": ["analytical", "analytical skills"],
    "attention to detail": ["detail oriented", "detail-oriented"],
    "leadership": ["led a team", "team lead", "team leader"],
}

# Roles used for job recommendations
ROLES = {
    "Python Developer": ["python", "django", "flask", "sql", "git", "rest api", "pytest", "docker"],
    "Full Stack Developer": ["javascript", "react", "node.js", "html", "css", "sql", "git", "rest api", "mongodb"],
    "Frontend Developer": ["html", "css", "javascript", "react", "typescript", "git", "figma", "bootstrap"],
    "Backend Developer": ["python", "java", "node.js", "sql", "rest api", "docker", "redis", "git", "microservices"],
    "Java Developer": ["java", "spring boot", "sql", "rest api", "microservices", "git", "junit", "maven"],
    "Data Analyst": ["sql", "excel", "python", "pandas", "tableau", "power bi", "data analysis", "statistics", "data visualization"],
    "Data Scientist": ["python", "machine learning", "pandas", "numpy", "scikit-learn", "statistics", "sql", "deep learning"],
    "Machine Learning Engineer": ["python", "tensorflow", "pytorch", "machine learning", "deep learning", "docker", "scikit-learn", "aws"],
    "AI / LLM Engineer": ["python", "llm", "prompt engineering", "generative ai", "natural language processing", "fastapi", "docker"],
    "DevOps Engineer": ["linux", "docker", "kubernetes", "ci/cd", "jenkins", "terraform", "aws", "bash", "git", "ansible"],
    "Cloud Engineer": ["aws", "azure", "google cloud", "terraform", "linux", "docker", "kubernetes", "networking"],
    "Mobile App Developer": ["android", "kotlin", "flutter", "react native", "firebase", "swift", "git", "rest api"],
    "QA / Test Engineer": ["selenium", "test automation", "pytest", "junit", "api testing", "postman", "jira", "agile"],
    "UI/UX Designer": ["figma", "wireframing", "prototyping", "user research", "html", "css"],
    "Cybersecurity Analyst": ["cybersecurity", "network security", "penetration testing", "siem", "linux", "python"],
}

ACTION_VERBS = {
    "achieved", "built", "created", "designed", "developed", "implemented", "improved", "increased", "reduced",
    "led", "managed", "optimized", "launched", "delivered", "automated", "analyzed", "collaborated", "deployed",
    "engineered", "integrated", "migrated", "mentored", "streamlined", "architected", "established", "resolved",
    "coordinated", "drove", "enhanced", "generated", "maintained", "organized", "presented", "refactored", "tested",
}

WEAK_PHRASES = ["responsible for", "worked on", "helped with", "duties included", "tasked with", "assisted in"]

DEGREE_RE = re.compile(
    r"\b(b\.?\s?tech|m\.?\s?tech|b\.?\s?e\b|m\.?\s?e\b|b\.?\s?sc|m\.?\s?sc|bca|mca|bba|mba|b\.?\s?com|m\.?\s?com|"
    r"bachelor(?:'s)?|master(?:'s)?|ph\.?\s?d|doctorate|diploma|associate degree|high school|hsc|ssc|"
    r"b\.?\s?a\b|m\.?\s?a\b)", re.I)
INSTITUTION_RE = re.compile(r"\b(university|college|institute|school|academy|iit|nit)\b", re.I)

STOPWORDS = set("""
a an the and or of to in on for with by at from as is are was were be been being this that these those it its
we you your our their they he she i will would can could should may might must shall do does did have has had
not no nor so than then too very just also into over under about across after before between during without
within through per via etc including include includes such other any all each both either more most less least
experience experienced work working works team teams ability able strong skills skill looking candidate role job
responsibilities responsibility requirements requirement years year knowledge required preferred good great plus
excellent understanding proven demonstrated seeking join company position opportunity ideal using use used
well new help make ensure related relevant based high level environment business development develop develops
developing support supporting provide providing ability candidates applicants apply responsible duties qualifications
""".split())
GENERIC_JD_WORDS = {"salary", "benefits", "location", "remote", "hybrid", "office", "full", "time", "part", "apply", "equal", "employer"}


def _compile(canon_list, aliases, skip_self=()):
    out = []
    for canon in canon_list:
        names = ([] if canon in skip_self else [canon]) + aliases.get(canon, [])
        alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        out.append((canon, re.compile(rf"(?<![a-z0-9+#])(?:{alt})(?![a-z0-9+#])")))
    return out


TECH_PATTERNS = _compile(TECH, TECH_ALIASES, skip_self=("go",))
SOFT_PATTERNS = _compile(SOFT, SOFT_ALIASES)
