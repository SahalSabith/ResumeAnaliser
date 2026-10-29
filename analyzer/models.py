import os
import re
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


def private_storage():
    """Files are stored outside STATIC/MEDIA, so no URL can ever expose them."""
    return FileSystemStorage(location=str(settings.PRIVATE_MEDIA_ROOT))


def upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"user_{instance.user_id}/{uuid.uuid4().hex}{ext}"  # random name, original never used on disk


class Resume(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="resumes")
    original_name = models.CharField(max_length=255)
    file = models.FileField(storage=private_storage, upload_to=upload_to, blank=True)
    extracted_text = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_name

    @property
    def has_file(self):
        return bool(self.file)

    def delete_file(self):
        if self.file:
            self.file.delete(save=False)
            self.file = ""
            self.save(update_fields=["file"])


@receiver(post_delete, sender=Resume)
def _remove_file_on_delete(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


class Analysis(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="analyses")
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="analyses")
    job_title = models.CharField(max_length=120, blank=True)
    job_description = models.TextField(blank=True)
    overall_score = models.PositiveSmallIntegerField(default=0)
    skills_score = models.PositiveSmallIntegerField(default=0)
    education_score = models.PositiveSmallIntegerField(default=0)
    format_score = models.PositiveSmallIntegerField(default=0)
    keyword_score = models.PositiveSmallIntegerField(default=0)
    match_score = models.PositiveSmallIntegerField(null=True, blank=True)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "analyses"

    def __str__(self):
        return f"{self.resume.original_name} - {self.overall_score}"

    @property
    def label(self):
        s = self.overall_score
        return "Excellent" if s >= 80 else "Good" if s >= 65 else "Fair" if s >= 50 else "Needs work"

    @property
    def band(self):
        s = self.overall_score
        return "good" if s >= 65 else "fair" if s >= 50 else "low"


# ------------------------------------------------------------------ resume builder
def _blocks(text):
    blocks = []
    for chunk in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [l.strip() for l in chunk.splitlines() if l.strip()]
        if not lines:
            continue
        parts = [p.strip() for p in lines[0].split("|") if p.strip()]
        bullets = [re.sub(r"^[-•*]\s*", "", l) for l in lines[1:]]
        blocks.append({"parts": parts or [lines[0]], "bullets": bullets})
    return blocks


class BuiltResume(models.Model):
    TEMPLATES = [("classic", "Classic"), ("modern", "Modern"), ("minimal", "Minimal")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="built_resumes")
    title = models.CharField("Resume name", max_length=120)
    template = models.CharField(max_length=20, choices=TEMPLATES, default="classic")
    full_name = models.CharField(max_length=100)
    headline = models.CharField("Professional headline", max_length=140, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    location = models.CharField(max_length=100, blank=True)
    links = models.CharField("Links (LinkedIn, GitHub, portfolio)", max_length=255, blank=True)
    summary = models.TextField(max_length=1200, blank=True)
    skills = models.TextField(blank=True, help_text="Comma-separated, e.g. Python, Django, SQL")
    experience = models.TextField(blank=True)
    education = models.TextField(blank=True)
    projects = models.TextField(blank=True)
    certifications = models.TextField(blank=True, help_text="One per line")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    @property
    def contact_list(self):
        items = [self.email, self.phone, self.location]
        items += [l.strip() for l in re.split(r"[,\n;]", self.links) if l.strip()]
        return [i for i in items if i]

    @property
    def skill_list(self):
        return [s.strip() for s in re.split(r"[,\n]", self.skills) if s.strip()]

    @property
    def experience_blocks(self):
        return _blocks(self.experience)

    @property
    def education_blocks(self):
        return _blocks(self.education)

    @property
    def project_blocks(self):
        return _blocks(self.projects)

    @property
    def cert_list(self):
        return [c.strip() for c in self.certifications.splitlines() if c.strip()]

    def as_plain_text(self):
        """Used so a built resume can be scored by the analyzer."""
        out = [self.full_name, self.headline, " ".join(self.contact_list)]
        if self.summary:
            out += ["Summary", self.summary]
        if self.skills:
            out += ["Skills", ", ".join(self.skill_list)]
        for title, txt in (("Experience", self.experience), ("Education", self.education),
                           ("Projects", self.projects), ("Certifications", self.certifications)):
            if txt.strip():
                out += [title, txt]
        return "\n".join(out)
