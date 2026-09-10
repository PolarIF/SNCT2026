"""Move para o banco o único link de inscrição que já existia no HTML.

O IFROmatizando estava com o endereço do SUAP escrito no template. Agora que
a inscrição é dado, ele passa para a área de Informática — senão a migração
faria o site perder o único link que já funcionava.
"""

from django.db import migrations

LINK = "https://suap.ifro.edu.br/eventos/inscricao/1/1229/"


def aplicar(apps, schema_editor):
    Area = apps.get_model("eventos", "Area")
    Area.objects.filter(slug="informatica", link_inscricao="").update(
        link_inscricao=LINK, inscricoes_abertas=True
    )


def desfazer(apps, schema_editor):
    Area = apps.get_model("eventos", "Area")
    Area.objects.filter(slug="informatica", link_inscricao=LINK).update(
        link_inscricao="", inscricoes_abertas=False
    )


class Migration(migrations.Migration):
    dependencies = [("eventos", "0003_inscricao_por_area")]

    operations = [migrations.RunPython(aplicar, desfazer)]
