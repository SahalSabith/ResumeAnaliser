from django.urls import path

from . import views

app_name = "analyzer"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("analyze/", views.analyze, name="analyze"),
    path("analysis/<int:pk>/", views.detail, name="detail"),
    path("analysis/<int:pk>/rematch/", views.rematch, name="rematch"),
    path("analysis/<int:pk>/delete/", views.analysis_delete, name="analysis_delete"),
    path("analysis/<int:pk>/report.pdf", views.report_pdf, name="report"),
    path("history/", views.history, name="history"),
    path("resume/<int:pk>/file/", views.resume_file, name="resume_file"),
    path("resume/<int:pk>/file/delete/", views.resume_file_delete, name="resume_file_delete"),
    path("resume/<int:pk>/delete/", views.resume_purge, name="resume_purge"),
    path("tools/", views.tools, name="tools"),
    path("builder/", views.builder_list, name="builder_list"),
    path("builder/new/", views.builder_edit, name="builder_new"),
    path("builder/suggest-summary/", views.builder_suggest, name="builder_suggest"),
    path("builder/<int:pk>/edit/", views.builder_edit, name="builder_edit"),
    path("builder/<int:pk>/preview/", views.builder_preview, name="builder_preview"),
    path("builder/<int:pk>/docx/", views.builder_docx, name="builder_docx"),
    path("builder/<int:pk>/analyze/", views.builder_analyze, name="builder_analyze"),
    path("builder/<int:pk>/delete/", views.builder_delete, name="builder_delete"),
]
