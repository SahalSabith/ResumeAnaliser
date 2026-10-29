from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.SecureLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("me/", views.account, name="account"),
    path("me/delete/", views.delete_account, name="delete"),
    path("me/password/", views.ChangePasswordView.as_view(), name="password_change"),
]
