from django.conf import settings


def ai_status(request):
    return {"AI_AVAILABLE": bool(settings.GEMINI_API_KEY), "MAX_UPLOAD_MB": settings.MAX_UPLOAD_MB}
