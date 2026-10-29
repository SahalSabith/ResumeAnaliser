import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label="Full name", max_length=60)
    email = forms.EmailField(label="Email address")
    accept_privacy = forms.BooleanField(
        label="I understand my resumes are private and I can delete them at any time.",
        error_messages={"required": "Please confirm to continue."},
    )

    class Meta:
        model = User
        fields = ("first_name", "username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = "4-30 characters: letters, numbers and underscores."
        self.fields["password1"].help_text = "At least 8 characters. Avoid common or all-numeric passwords."
        self.fields["first_name"].widget.attrs.update(autocomplete="name")
        self.fields["email"].widget.attrs.update(autocomplete="email")
        self.fields["username"].widget.attrs.update(autocomplete="username", minlength=4)
        self.fields["password1"].widget.attrs.update(autocomplete="new-password", minlength=8)
        self.fields["password2"].widget.attrs.update(autocomplete="new-password", minlength=8)

    def clean_first_name(self):
        name = " ".join(self.cleaned_data["first_name"].split())
        if len(name) < 2 or not re.match(r"^[A-Za-z .'-]+$", name):
            raise forms.ValidationError("Enter your real name using letters only.")
        return name

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if not re.match(r"^[A-Za-z0-9_]{4,30}$", username):
            raise forms.ValidationError("Use 4-30 letters, numbers or underscores (no spaces).")
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username or email", max_length=150)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(autocomplete="username", autofocus=True)
        self.error_messages["invalid_login"] = "Wrong username/email or password. Check both and try again."

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        if "@" in value:
            user = User.objects.filter(email__iexact=value).first()
            if user:
                return user.get_username()
        return value


class DeleteAccountForm(forms.Form):
    password = forms.CharField(label="Confirm your password", widget=forms.PasswordInput)
