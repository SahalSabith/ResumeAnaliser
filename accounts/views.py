from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .forms import DeleteAccountForm, LoginForm, RegisterForm

MAX_ATTEMPTS = 5
LOCK_SECONDS = 300


def _fail_key(request, username):
    ip = request.META.get("REMOTE_ADDR", "?")
    return f"login_fail:{ip}:{(username or '').strip().lower()}"


class SecureLoginView(LoginView):
    """Login with brute-force protection (5 failures -> 5 minute lock)."""
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        key = _fail_key(request, request.POST.get("username"))
        if cache.get(key, 0) >= MAX_ATTEMPTS:
            messages.error(request, "Too many failed attempts. Please wait 5 minutes and try again.")
            return self.get(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = _fail_key(self.request, self.request.POST.get("username"))
        cache.set(key, cache.get(key, 0) + 1, LOCK_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_fail_key(self.request, self.request.POST.get("username")))
        return super().form_valid(form)


def register(request):
    if request.user.is_authenticated:
        return redirect("analyzer:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.email = form.cleaned_data["email"]
        user.save()
        login(request, user)
        messages.success(request, f"Welcome, {user.first_name}! Upload your first resume to get started.")
        return redirect("analyzer:analyze")
    return render(request, "accounts/register.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("analyzer:home")


@login_required
def account(request):
    return render(request, "accounts/account.html", {
        "resume_count": request.user.resumes.count(),
        "analysis_count": request.user.analyses.count(),
        "delete_form": DeleteAccountForm(),
    })


@login_required
@require_POST
def delete_account(request):
    form = DeleteAccountForm(request.POST)
    if form.is_valid() and request.user.check_password(form.cleaned_data["password"]):
        user = request.user
        logout(request)
        user.delete()  # cascades: resumes, analyses; signal removes uploaded files
        messages.success(request, "Your account and all stored resumes were permanently deleted.")
        return redirect("analyzer:home")
    messages.error(request, "Password incorrect. Your account was not deleted.")
    return redirect("accounts:account")


class ChangePasswordView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:account")

    def form_valid(self, form):
        messages.success(self.request, "Password updated.")
        return super().form_valid(form)
