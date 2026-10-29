# ResumeIQ: AI Resume Analyzer (Django + SQLite)

Full-stack Django project using Django Template Language. Upload a PDF/DOCX resume, get a score, detected
skills, job-description matching, missing skills, improvement tips, job recommendations and a downloadable PDF
report. Also includes a resume builder (3 templates) and writing tools.

## Run it

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # optional: add a free Gemini key
python manage.py migrate
python manage.py createsuperuser  # optional, for /admin
python manage.py runserver
```

Open http://127.0.0.1:8000 and register an account.

Run the tests: `python manage.py test`

## Free AI

The app works fully offline using its built-in analyzer. For richer feedback, add a **free** Google Gemini key:

1. Get a key at https://aistudio.google.com/apikey (free tier, no card needed at time of writing)
2. Put it in `.env` as `GEMINI_API_KEY=...`
3. Tick "Add AI feedback" when analyzing, or use the Writing tools

If the AI call fails or hits the free quota, the app falls back to the local analyzer automatically.
Change the model with `GEMINI_MODEL` if Google renames it.

## Privacy design

| Measure | Where |
|---|---|
| Uploads stored in `private_uploads/`, outside static/media, random filenames | `analyzer/models.py` |
| Every query is filtered by `user=request.user`; others get 404 | `analyzer/views.py` |
| Files are only served through an owner-checked view, `no-store` | `resume_file` view |
| Delete original file only / delete everything / delete account (files removed from disk) | History + Account pages |
| Option to delete the file immediately after analysis | Upload form |
| AI is opt-in; email, phone and links are stripped before sending | `services/ai.py` |
| Magic-byte file check, size limit, zip-bomb guard | `forms.py`, `services/extract.py` |
| CSRF, HttpOnly/SameSite cookies, clickjacking and nosniff headers, login lockout | `settings.py`, `accounts/views.py` |
| Admin hides resume text and analysis data | `analyzer/admin.py` |

## Login validations

Required full name (letters only), unique username (4-30 letters/numbers/underscore), unique email, Django password
validators (min 8, not common, not numeric, not similar to your details), password confirmation, privacy checkbox.
Login accepts username or email and locks for 5 minutes after 5 failures.

## Structure

```
config/            settings, urls
accounts/          register, login (throttled), account, delete account
analyzer/
  models.py        Resume, Analysis, BuiltResume
  views.py         dashboard, analyze, detail, history, reports, tools, builder
  services/
    extract.py     PDF/DOCX text extraction
    skills_data.py skill dictionaries, roles
    scoring.py     parsing, scoring, JD match, suggestions, job recommendations
    ai.py          Gemini (free tier) + local fallback
    reports.py     PDF report, DOCX export
templates/ static/ HTML (Django templates) and CSS
```

## Before deploying

Set `DJANGO_DEBUG=0`, a long random `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`, serve over HTTPS, run
`python manage.py collectstatic`, and use gunicorn behind nginx. For multiple server processes, switch the cache in
`settings.py` to Redis/database so the login lockout is shared.
