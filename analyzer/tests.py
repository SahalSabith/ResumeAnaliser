import io

import docx
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Analysis, Resume
from .services import scoring

User = get_user_model()

SAMPLE = """Asha Rao
asha@example.com | +91 98765 43210 | linkedin.com/in/asha | github.com/asha

Summary
Python developer with 2 years of experience building web apps.

Skills
Python, Django, SQL, Git, Docker, REST API, React, JavaScript, Teamwork, Communication

Experience
Software Intern | Acme | 2023 - 2025
- Built a REST API that served 5000 users and reduced load time by 35%
- Automated reports, saving 10 hours per week
- Led a team of 3 interns

Projects
Resume Analyzer
- Developed a Django app with SQLite

Education
B.Tech Computer Science, ABC Institute of Technology, 2020 - 2024, CGPA 8.4
""" + "\nExtra filler line for length. " * 40


def make_docx(text):
    d = docx.Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class ScoringTests(TestCase):
    def test_parse_and_score(self):
        out = scoring.analyze(SAMPLE, "We need a Python Django developer with SQL, Kubernetes and AWS. 3+ years experience.")
        self.assertIn("python", out["parsed"]["tech_skills"])
        self.assertIn("django", out["parsed"]["tech_skills"])
        self.assertGreater(out["scores"]["overall"], 55)
        self.assertIn("kubernetes", out["match"]["missing_skills"])
        self.assertIn("aws", out["match"]["missing_skills"])
        self.assertTrue(out["jobs"])
        self.assertEqual(out["jobs"][0]["role"] in ("Python Developer", "Backend Developer", "Full Stack Developer"), True)

    def test_empty_jd_means_no_match(self):
        self.assertIsNone(scoring.analyze(SAMPLE, "")["match"])


class AccountTests(TestCase):
    def test_register_validation(self):
        User.objects.create_user("taken_user", "dup@example.com", "Str0ng!pass99")
        r = self.client.post(reverse("accounts:register"), {
            "first_name": "Bob", "username": "bob_1", "email": "dup@example.com",
            "password1": "12345678", "password2": "12345678", "accept_privacy": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "already exists")
        self.assertFalse(User.objects.filter(username="bob_1").exists())

    def test_register_and_login_by_email(self):
        self.client.post(reverse("accounts:register"), {
            "first_name": "Bob", "username": "bob_1", "email": "bob@example.com",
            "password1": "Tr1cky-pass-77", "password2": "Tr1cky-pass-77", "accept_privacy": "on"})
        self.client.get(reverse("accounts:login"))
        self.client.post(reverse("accounts:logout"))
        r = self.client.post(reverse("accounts:login"), {"username": "bob@example.com", "password": "Tr1cky-pass-77"})
        self.assertEqual(r.status_code, 302)

    def test_login_lockout(self):
        User.objects.create_user("lock_me", "l@example.com", "Str0ng!pass99")
        for _ in range(5):
            self.client.post(reverse("accounts:login"), {"username": "lock_me", "password": "wrong"})
        r = self.client.post(reverse("accounts:login"), {"username": "lock_me", "password": "Str0ng!pass99"})
        self.assertEqual(r.status_code, 200)  # locked, not redirected
        self.assertContains(r, "Too many failed attempts")

    def test_pages_require_login(self):
        for name in ("analyzer:dashboard", "analyzer:analyze", "analyzer:history", "analyzer:tools", "analyzer:builder_list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)


class UploadPrivacyTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice_a", "a@example.com", "Str0ng!pass99", first_name="Alice")
        self.mallory = User.objects.create_user("mallory", "m@example.com", "Str0ng!pass99", first_name="Mallory")

    def tearDown(self):
        User.objects.all().delete()  # cascades and removes files from disk

    def upload(self, name="cv.docx", data=None, **extra):
        self.client.force_login(self.alice)
        f = SimpleUploadedFile(name, data or make_docx(SAMPLE))
        return self.client.post(reverse("analyzer:analyze"), {"resume": f, **extra})

    def test_upload_analysis_report(self):
        r = self.upload(job_description="Looking for Python and Django developer with SQL knowledge and Docker.")
        a = Analysis.objects.get()
        self.assertRedirects(r, reverse("analyzer:detail", args=[a.pk]))
        self.assertIsNotNone(a.match_score)
        self.assertEqual(self.client.get(reverse("analyzer:detail", args=[a.pk])).status_code, 200)
        pdf = self.client.get(reverse("analyzer:report", args=[a.pk]))
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_rejects_bad_files(self):
        self.upload(name="cv.exe", data=b"MZ" + b"0" * 800)
        self.upload(name="fake.pdf", data=b"not a pdf at all " * 60)
        self.assertEqual(Resume.objects.count(), 0)

    def test_other_users_cannot_access(self):
        self.upload()
        a = Analysis.objects.get()
        self.client.force_login(self.mallory)
        self.assertEqual(self.client.get(reverse("analyzer:detail", args=[a.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("analyzer:report", args=[a.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("analyzer:resume_file", args=[a.resume.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("analyzer:resume_purge", args=[a.resume.pk])).status_code, 404)

    def test_owner_download_and_delete_file(self):
        self.upload()
        res = Resume.objects.get()
        path = res.file.path
        self.assertEqual(self.client.get(reverse("analyzer:resume_file", args=[res.pk])).status_code, 200)
        self.client.post(reverse("analyzer:resume_file_delete", args=[res.pk]))
        res.refresh_from_db()
        self.assertFalse(res.has_file)
        import os
        self.assertFalse(os.path.exists(path))
        self.assertEqual(Analysis.objects.count(), 1)  # analysis survives file deletion

    def test_delete_after_option(self):
        self.upload(delete_after="on")
        self.assertFalse(Resume.objects.get().has_file)


class BuilderToolTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("builder1", "b@example.com", "Str0ng!pass99", first_name="Bee")
        self.client.force_login(self.u)

    def test_build_preview_docx(self):
        r = self.client.post(reverse("analyzer:builder_new"), {
            "title": "Main", "template": "modern", "full_name": "Bee Kay", "email": "b@example.com",
            "phone": "+91 99999 11111", "skills": "Python, SQL", "experience": "Dev | Co | 2024\n- Built things 40% faster"})
        self.assertEqual(r.status_code, 302)
        for t in ("classic", "modern", "minimal"):
            resp = self.client.get(r["Location"] + f"?t={t}")
            self.assertContains(resp, "Bee Kay")
            self.assertContains(resp, "Built things")
        pk = self.u.built_resumes.get().pk
        self.assertEqual(self.client.get(reverse("analyzer:builder_docx", args=[pk])).status_code, 200)

    def test_bad_phone_rejected(self):
        r = self.client.post(reverse("analyzer:builder_new"), {"title": "x", "template": "classic", "full_name": "Bee Kay", "phone": "12"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "valid phone")

    def test_local_tools(self):
        r = self.client.post(reverse("analyzer:tools"), {"tool": "bullet", "bullet": "responsible for managing the website"})
        self.assertContains(r, "Led managing the website")
        r = self.client.post(reverse("analyzer:tools"), {"tool": "cover", "role": "Python Developer", "company": "Acme", "skills": "Python, SQL"})
        self.assertContains(r, "Acme")
