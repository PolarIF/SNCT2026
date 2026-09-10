from django.contrib import admin
from django.urls import include, path

from eventos import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cronograma/", views.cronograma, name="cronograma"),
    path("saude/", views.saude, name="saude"),
    path("painel/", include("eventos.urls")),
    path("admin/", admin.site.urls),
]

admin.site.site_header = "SNCT — IFRO Campus Ariquemes"
admin.site.site_title = "SNCT IFRO"
admin.site.index_title = "Administração do site"
