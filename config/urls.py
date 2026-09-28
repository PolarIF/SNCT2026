from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from eventos import views

urlpatterns = [
    path("", views.home, name="home"),
    path("trabalhos/", views.trabalhos, name="trabalhos"),
    path("trabalhos/<slug:slug>/", views.documento, name="documento"),
    path("cronograma/", views.cronograma, name="cronograma"),
    path("saude/", views.saude, name="saude"),
    path("painel/", include("eventos.urls")),
    path("admin/", admin.site.urls),
    # Os anexos da submissão são enviados depois do deploy, então não passam
    # pelo collectstatic nem pelo whitenoise — quem os serve é o Django. São
    # meia dúzia de PDFs baixados algumas vezes por dia; o proxy da frente já
    # comprime e o custo é irrelevante. `serve` resolve o caminho dentro de
    # MEDIA_ROOT e recusa qualquer ".." no meio.
    re_path(
        r"^midia/(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
        name="midia",
    ),
]

if settings.METRICS_ATIVO:
    # /metrics para o Prometheus. Sem autenticação — quem publica o site é
    # responsável por não deixar esta rota chegar à internet (IMPLANTACAO.md).
    urlpatterns.append(path("", include("django_prometheus.urls")))

admin.site.site_header = "SNCT — IFRO Campus Ariquemes"
admin.site.site_title = "SNCT IFRO"
admin.site.index_title = "Administração do site"
