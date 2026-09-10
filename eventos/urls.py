from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "painel"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("inscricao/<slug:slug>/", views.inscricao, name="inscricao"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            template_name="painel/entrar.html",
            redirect_authenticated_user=True,
        ),
        name="entrar",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="sair"),
]
