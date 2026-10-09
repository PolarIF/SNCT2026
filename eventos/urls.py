from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "painel"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("inscricao/<slug:slug>/", views.inscricao, name="inscricao"),
    path("submissao/<slug:slug>/", views.submissao, name="submissao"),
    path("anexos/", views.anexos, name="anexos"),
    path("anexos/novo/", views.anexo_novo, name="anexo_novo"),
    path("anexos/<int:pk>/editar/", views.anexo_editar, name="anexo_editar"),
    path("anexos/<int:pk>/excluir/", views.anexo_excluir, name="anexo_excluir"),
    path("cartoes/", views.cartoes, name="cartoes"),
    path("cartoes/novo/", views.cartao_novo, name="cartao_novo"),
    path("cartoes/<int:pk>/editar/", views.cartao_editar, name="cartao_editar"),
    path("cartoes/<int:pk>/excluir/", views.cartao_excluir, name="cartao_excluir"),
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
