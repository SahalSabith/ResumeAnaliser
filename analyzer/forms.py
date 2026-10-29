import os
import re

from django import forms
from django.conf import settings

from .models import BuiltResume
from .services.extract import looks_like


class UploadForm(forms.Form):
    resume = forms.FileField(label="Resume file (PDF or DOCX)")
    job_title = forms.CharField(label="Target job title (optional)", max_length=120, required=False)
    job_description = forms.CharField(
        label="Job description (optional)", required=False, max_length=8000,
        widget=forms.Textarea(attrs={"rows": 7, "placeholder": "Paste the job posting here to get a match score and missing skills."}))
    delete_after = forms.BooleanField(
        label="Delete the original file right after analysis (only the extracted text is kept)", required=False)

    def clean_resume(self):
        f = self.cleaned_data["resume"]
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in (".pdf", ".docx"):
            raise forms.ValidationError("Only PDF and DOCX files are accepted.")
        if f.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"File is larger than {settings.MAX_UPLOAD_MB} MB.")
        if f.size < 500:
            raise forms.ValidationError("This file looks empty.")
        head = f.read(8)
        f.seek(0)
        if not looks_like(ext, head):
            raise forms.ValidationError(f"This file isn't a valid {ext[1:].upper()}. Re-export it and try again.")
        return f

    def clean_job_description(self):
        return self.cleaned_data["job_description"].strip()


class RematchForm(forms.Form):
    job_title = forms.CharField(max_length=120, required=False)
    job_description = forms.CharField(min_length=30, max_length=8000,
                                      error_messages={"min_length": "Paste at least a few sentences of the job description."})


class BuiltResumeForm(forms.ModelForm):
    class Meta:
        model = BuiltResume
        fields = ["title", "template", "full_name", "headline", "email", "phone", "location", "links",
                  "summary", "skills", "experience", "education", "projects", "certifications"]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
            "skills": forms.Textarea(attrs={"rows": 2, "placeholder": "Python, Django, SQL, Git"}),
            "experience": forms.Textarea(attrs={"rows": 9, "placeholder": "Software Intern | Acme Pvt Ltd | Jun 2025 - Aug 2025\n- Built a REST API serving 5k daily requests\n- Cut report time by 40% by automating exports\n\nNext role | Company | Dates\n- First bullet"}),
            "education": forms.Textarea(attrs={"rows": 4, "placeholder": "B.Tech Computer Science | ABC Institute | 2022 - 2026\n- CGPA 8.4"}),
            "projects": forms.Textarea(attrs={"rows": 6, "placeholder": "Resume Analyzer | Django, SQLite\n- Scores resumes and matches them to job descriptions"}),
            "certifications": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "experience": "One block per role. First line: Title | Company | Dates. Next lines: bullets. Blank line between roles.",
            "education": "Same format: first line Degree | Institution | Years, then optional bullets.",
            "projects": "Same format: first line Name | Tech used, then bullets.",
        }

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if len(name) < 2:
            raise forms.ValidationError("Enter your full name.")
        return name

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if phone and not 10 <= len(re.sub(r"\D", "", phone)) <= 13:
            raise forms.ValidationError("Enter a valid phone number (10-13 digits).")
        return phone
