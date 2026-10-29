from django.contrib import admin

from .models import Analysis, BuiltResume, Resume

# NOTE: resume text/data is deliberately not exposed in the admin list views.
admin.site.register(Resume, list_display=("original_name", "user", "uploaded_at"), exclude=("extracted_text",))
admin.site.register(Analysis, list_display=("resume", "user", "overall_score", "match_score", "created_at"),
                    exclude=("data", "job_description"))
admin.site.register(BuiltResume, list_display=("title", "user", "template", "updated_at"))
