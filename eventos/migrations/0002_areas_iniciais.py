"""Cria os cursos/áreas que já apareciam na página, para o sistema nascer usável.

Só roda se a tabela estiver vazia — quem renomear ou apagar áreas depois não
vai vê-las voltando no próximo deploy.
"""

from django.db import migrations
from django.utils.text import slugify

AREAS = [
    "Geral",
    "CIEEC",
    "Agronomia e Agropecuária",
    "Alimentos",
    "Informática",
    "Biologia",
    "Medicina Veterinária",
]


def criar(apps, schema_editor):
    Area = apps.get_model("eventos", "Area")
    if Area.objects.exists():
        return
    Area.objects.bulk_create(
        [Area(nome=nome, slug=slugify(nome)[:80], ativo=True) for nome in AREAS]
    )


def desfazer(apps, schema_editor):
    Area = apps.get_model("eventos", "Area")
    Area.objects.filter(nome__in=AREAS, eventos__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("eventos", "0001_initial")]

    operations = [migrations.RunPython(criar, desfazer)]
