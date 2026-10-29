import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BuiltResumeForm, RematchForm, UploadForm
from .models import Analysis, BuiltResume, Resume
from .services import ai, reports, scoring
from .services.extract import ExtractionError, extract_text


def home(request):
    if request.user.is_authenticated:
        return redirect("analyzer:dashboard")
    return render(request, "analyzer/home.html")


# ------------------------------------------------------------------ analysis core
def _run_analysis(user, resume, job_title, jd, use_ai):
    data = scoring.analyze(resume.extracted_text, jd)
    review = ai.review_resume(resume.extracted_text, jd) if (use_ai and ai.ai_enabled()) else None
    if review:
        for s in review["suggestions"]:
            if s["title"]:
                data["suggestions"].append({"priority": "medium", "title": s["title"], "detail": s["detail"], "source": "ai"})
    data["ai"] = review
    sc, match = data["scores"], data["match"]
    return Analysis.objects.create(
        user=user, resume=resume, job_title=job_title, job_description=jd,
        overall_score=sc["overall"], skills_score=sc["skills"], education_score=sc["education"],
        format_score=sc["format"], keyword_score=sc["keywords"],
        match_score=match["score"] if match else None, data=data)


@login_required
def dashboard(request):
    qs = request.user.analyses.select_related("resume")
    latest = qs.first()
    recent = list(qs[:6])
    context = {
        "latest": latest,
        "recent": recent,
        "trend": list(reversed(recent)),
        "total_analyses": qs.count(),
        "total_resumes": request.user.resumes.count(),
        "avg_score": round(qs.aggregate(v=Avg("overall_score"))["v"] or 0),
        "best_match": qs.exclude(match_score=None).order_by("-match_score").first(),
        "built_count": request.user.built_resumes.count(),
    }
    return render(request, "analyzer/dashboard.html", context)


@login_required
def analyze(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        f = form.cleaned_data["resume"]
        ext = os.path.splitext(f.name)[1].lower()
        resume = Resume(user=request.user, original_name=os.path.basename(f.name)[:255])
        resume.file.save(f.name, f, save=False)
        resume.save()
        try:
            text = extract_text(resume.file.path, ext)
        except ExtractionError as exc:
            resume.delete()
            form.add_error("resume", str(exc))
        else:
            if len(text.strip()) < 80:
                resume.delete()
                form.add_error("resume", "We couldn't find readable text. Scanned or image-only resumes aren't supported. Export a text-based PDF or DOCX.")
            else:
                resume.extracted_text = text[:40000]
                resume.save(update_fields=["extracted_text"])
                analysis = _run_analysis(request.user, resume, form.cleaned_data["job_title"],
                                         form.cleaned_data["job_description"], form.cleaned_data["use_ai"])
                if form.cleaned_data["delete_after"]:
                    resume.delete_file()
                    messages.info(request, "Original file deleted. Only the extracted text remains in your account.")
                if form.cleaned_data["use_ai"] and not analysis.data.get("ai"):
                    messages.warning(request, "AI feedback wasn't available right now, so you're seeing the built-in analysis.")
                return redirect("analyzer:detail", pk=analysis.pk)
    return render(request, "analyzer/upload.html", {"form": form})


@login_required
def detail(request, pk):
    a = get_object_or_404(Analysis.objects.select_related("resume"), pk=pk, user=request.user)
    return render(request, "analyzer/detail.html", {"a": a, "d": a.data, "rematch": RematchForm()})


@login_required
@require_POST
def rematch(request, pk):
    a = get_object_or_404(Analysis.objects.select_related("resume"), pk=pk, user=request.user)
    form = RematchForm(request.POST)
    if not form.is_valid():
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
        return redirect("analyzer:detail", pk=pk)
    new = _run_analysis(request.user, a.resume, form.cleaned_data["job_title"],
                        form.cleaned_data["job_description"].strip(), form.cleaned_data["use_ai"])
    messages.success(request, "Matched against the new job description.")
    return redirect("analyzer:detail", pk=new.pk)


@login_required
def history(request):
    page = Paginator(request.user.analyses.select_related("resume"), 10).get_page(request.GET.get("page"))
    return render(request, "analyzer/history.html", {"page": page, "resumes": request.user.resumes.all()})


@login_required
@require_POST
def analysis_delete(request, pk):
    get_object_or_404(Analysis, pk=pk, user=request.user).delete()
    messages.success(request, "Analysis deleted.")
    return redirect("analyzer:history")


@login_required
def report_pdf(request, pk):
    a = get_object_or_404(Analysis.objects.select_related("resume"), pk=pk, user=request.user)
    resp = HttpResponse(reports.build_pdf(a), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="resume-report-{a.pk}.pdf"'
    return resp


# ------------------------------------------------------------------ privacy: files only ever served to their owner
@login_required
def resume_file(request, pk):
    r = get_object_or_404(Resume, pk=pk, user=request.user)
    if not r.has_file:
        raise Http404("The original file was deleted.")
    resp = FileResponse(r.file.open("rb"), as_attachment=True, filename=r.original_name)
    resp["Cache-Control"] = "private, no-store"
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


@login_required
@require_POST
def resume_file_delete(request, pk):
    get_object_or_404(Resume, pk=pk, user=request.user).delete_file()
    messages.success(request, "Original file permanently deleted.")
    return redirect("analyzer:history")


@login_required
@require_POST
def resume_purge(request, pk):
    get_object_or_404(Resume, pk=pk, user=request.user).delete()  # file + text + analyses
    messages.success(request, "Resume, extracted text and its analyses were permanently deleted.")
    return redirect("analyzer:history")


# ------------------------------------------------------------------ helper tools
@login_required
def tools(request):
    result, tool = None, request.POST.get("tool")
    if request.method == "POST":
        use_ai = bool(request.POST.get("use_ai"))
        g = lambda k: request.POST.get(k, "").strip()
        if tool == "bullet" and len(g("bullet")) >= 5:
            result = ai.improve_bullet(g("bullet")[:600], use_ai)
        elif tool == "summary" and g("role"):
            text, used = ai.generate_summary(g("role")[:80], g("skills")[:300], g("years")[:10], use_ai)
            result = {"text": text, "ai": used}
        elif tool == "cover" and g("role"):
            text, used = ai.cover_letter(g("role")[:80], g("company")[:80], g("skills")[:300], g("jd")[:3000],
                                         request.user.first_name, use_ai)
            result = {"text": text, "ai": used}
        else:
            messages.error(request, "Please fill in the required fields for that tool.")
            tool = None
    return render(request, "analyzer/tools.html", {"result": result, "tool": tool, "post": request.POST})


# ------------------------------------------------------------------ resume builder
@login_required
def builder_list(request):
    return render(request, "analyzer/builder_list.html", {"items": request.user.built_resumes.all()})


@login_required
def builder_edit(request, pk=None):
    obj = get_object_or_404(BuiltResume, pk=pk, user=request.user) if pk else None
    initial = {} if obj else {"full_name": request.user.first_name, "email": request.user.email,
                               "title": "My resume"}
    form = BuiltResumeForm(request.POST or None, instance=obj, initial=initial)
    if request.method == "POST" and form.is_valid():
        r = form.save(commit=False)
        r.user = request.user
        r.save()
        messages.success(request, "Resume saved.")
        return redirect("analyzer:builder_preview", pk=r.pk)
    return render(request, "analyzer/builder_form.html", {"form": form, "obj": obj})


TEMPLATE_KEYS = ["classic", "modern", "minimal"]


@login_required
def builder_preview(request, pk):
    r = get_object_or_404(BuiltResume, pk=pk, user=request.user)
    t = request.GET.get("t", r.template)
    t = t if t in TEMPLATE_KEYS else r.template
    return render(request, "analyzer/builder_preview.html",
                  {"r": r, "t": t, "tpl": f"analyzer/resume_tpl/{t}.html", "keys": TEMPLATE_KEYS})


@login_required
def builder_docx(request, pk):
    r = get_object_or_404(BuiltResume, pk=pk, user=request.user)
    resp = HttpResponse(reports.build_docx(r),
                        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    resp["Content-Disposition"] = f'attachment; filename="{r.title[:40] or "resume"}.docx"'
    return resp


@login_required
@require_POST
def builder_delete(request, pk):
    get_object_or_404(BuiltResume, pk=pk, user=request.user).delete()
    messages.success(request, "Resume deleted.")
    return redirect("analyzer:builder_list")


@login_required
@require_POST
def builder_analyze(request, pk):
    """Score a built resume with the same analyzer (no file is stored)."""
    r = get_object_or_404(BuiltResume, pk=pk, user=request.user)
    resume = Resume.objects.create(user=request.user, original_name=f"{r.title} (built in ResumeIQ)",
                                   extracted_text=r.as_plain_text()[:40000])
    a = _run_analysis(request.user, resume, "", "", False)
    return redirect("analyzer:detail", pk=a.pk)


@login_required
@require_POST
def builder_suggest(request):
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "bad request"}, status=400)
    role = str(body.get("role", "")).strip()[:80]
    if not role:
        return JsonResponse({"error": "Enter a headline or target role first."}, status=400)
    text, used = ai.generate_summary(role, str(body.get("skills", ""))[:300], str(body.get("years", ""))[:10], True)
    return JsonResponse({"summary": text, "ai": used})
