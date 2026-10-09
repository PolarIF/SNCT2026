"""Transforma a submissão única na Mostra Científica e cria a segunda mostra.

O que já estava no ar passa inteiro para a Mostra Científica, que é o que
ele sempre foi: o link e o prazo, os documentos (regulamento e modelos) e as
quatro datas que estavam fixas no HTML de /trabalhos/. O texto da chamada da
página inicial também vem junto, porque agora cada mostra tem o seu.

A Mostra Empreendedora e Tecnológica nasce fechada, sem texto, sem link e
sem datas: a organização ainda não tinha nada disso quando esta migração foi
escrita. A página a mostra como "em breve" até alguém preencher pelo painel.
"""

from datetime import date

from django.core.management.color import no_style
from django.db import migrations

CIENTIFICA = "mostra-cientifica"
EMPREENDEDORA = "mostra-empreendedora-e-tecnologica"

# O texto que estava em templates/index.html, com o <b> virando **.
RESUMO_CIENTIFICA = (
    "Estudantes de todos os cursos podem inscrever seus trabalhos na SNCT! "
    "Os participantes poderão enviar **trabalhos completos** ou **resumos "
    "simples**, conforme as normas estabelecidas no Regulamento do evento.\n"
    "\n"
    "📌 Atenção: todos os trabalhos aprovados deverão ser obrigatoriamente "
    "apresentados na **modalidade banner**. Leia o regulamento antes de "
    "submeter seu trabalho."
)

# As quatro datas que estavam em templates/trabalhos.html.
ETAPAS_CIENTIFICA = [
    ("Submissão", date(2026, 9, 24), date(2026, 10, 12), "Envio dos trabalhos pelo formulário."),
    ("Avaliação", date(2026, 9, 24), date(2026, 10, 15), "Corre junto com o envio: quem manda cedo é avaliado cedo."),
    ("Correções", date(2026, 10, 16), date(2026, 10, 20), "Prazo para ajustar o que a avaliação apontar."),
    ("Resultado final", date(2026, 10, 22), None, "Divulgação dos trabalhos aprovados, na véspera da semana."),
]


def separa_as_mostras(apps, schema_editor):
    Submissao = apps.get_model("eventos", "Submissao")
    LinkDeEnvio = apps.get_model("eventos", "LinkDeEnvio")
    Etapa = apps.get_model("eventos", "Etapa")
    Anexo = apps.get_model("eventos", "Anexo")

    # A 0004 criou a linha 1; o get_or_create é para um banco em que alguém
    # a tenha apagado pelo shell.
    cientifica, _ = Submissao.objects.get_or_create(pk=1)
    cientifica.nome = "Mostra Científica"
    cientifica.slug = CIENTIFICA
    cientifica.resumo = RESUMO_CIENTIFICA
    cientifica.ordem = 0
    cientifica.save()

    if cientifica.link:
        LinkDeEnvio.objects.create(
            submissao=cientifica, rotulo="Enviar meu trabalho", url=cientifica.link
        )
    for titulo, inicio, fim, descricao in ETAPAS_CIENTIFICA:
        Etapa.objects.create(
            submissao=cientifica, titulo=titulo, inicio=inicio, fim=fim, descricao=descricao
        )

    # A linha 1 nasceu com o id escrito à mão (a 0004, e o save() antigo, que
    # forçava pk=1), e no PostgreSQL isso não anda o contador de ids da
    # tabela. Sem realinhar, a segunda mostra tentaria nascer com id 1 de
    # novo e a migração quebraria com "duplicate key". No SQLite isto não faz
    # nada — lá o próximo id sai do maior que já existe.
    for sql in schema_editor.connection.ops.sequence_reset_sql(no_style(), [Submissao]):
        schema_editor.execute(sql)

    Submissao.objects.create(
        nome="Mostra Empreendedora e Tecnológica",
        slug=EMPREENDEDORA,
        ordem=1,
    )

    Anexo.objects.update(submissao=cientifica)


def junta_de_novo(apps, schema_editor):
    """A volta: a Científica volta a ser a submissão única.

    O que for da Empreendedora se perde — do outro lado não há onde guardar.
    Documento dela não é apagado: passa para a Científica, porque arquivo
    enviado é trabalho de alguém.
    """
    Submissao = apps.get_model("eventos", "Submissao")
    Anexo = apps.get_model("eventos", "Anexo")

    cientifica = Submissao.objects.get(slug=CIENTIFICA)
    primeiro = cientifica.links.order_by("ordem", "pk").first()
    cientifica.link = primeiro.url if primeiro else ""
    cientifica.save()

    Anexo.objects.update(submissao=None)
    Submissao.objects.exclude(pk=cientifica.pk).delete()
    cientifica.links.all().delete()
    cientifica.etapas.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("eventos", "0012_submissao_por_mostra"),
    ]

    operations = [
        migrations.RunPython(separa_as_mostras, junta_de_novo),
    ]
