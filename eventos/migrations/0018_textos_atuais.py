"""Preenche os textos do site com o que estava escrito nos templates.

Ninguém deve notar diferença no dia em que esta migração rodar: cada texto
abaixo é o que estava no HTML. As exceções são três frases que já estavam
desatualizadas e foram corrigidas aqui mesmo:

- a nota do guia e o item "Trabalhos" da ficha diziam que a submissão era
  "uma só para a semana inteira" — agora são duas mostras;
- o passo 2 falava em "botão vermelho", e o botão é rosa desde o tema novo;
- o passo 3 terminava em "vale conferir mais perto de outubro".
"""

from datetime import date

from django.db import migrations

SITE = {
    "edicao": "23ª",
    "nome": "Semana Nacional de Ciência e Tecnologia",
    "tema": "Ciência Delas",
    "data_inicio": date(2026, 10, 27),
    "data_fim": date(2026, 10, 30),
    "local": "IFRO — Campus Ariquemes, Ariquemes (RO)",
    "heroi_texto": (
        "Quatro dias de feiras, oficinas, mostras e seminários abertos à "
        "comunidade escolar e ao público externo, no Instituto Federal de Rondônia."
    ),
    "programacao_titulo": "Como a semana se divide",
    "eventos_titulo": "Sete eventos, inscrição por evento",
    "eventos_texto": (
        "Cada evento tem inscrição própria. Veja abaixo o que cada um aborda, "
        "quem responde por ele e a programação resumida."
    ),
    "guia_titulo": "Como se inscrever",
    "guia_subtitulo": "Pelo SUAP, evento por evento — em três passos",
    "guia_nota": (
        "A submissão de trabalhos é outra coisa, com prazo e formulário "
        "próprios de cada mostra: [ver como enviar](#trabalhos)."
    ),
    "sobre_titulo": "Uma semana para mostrar o que se faz aqui",
    "sobre_texto": (
        "A Semana Nacional de Ciência e Tecnologia é um evento anual que integra "
        "pesquisa, extensão e ensino técnico. No IFRO Campus Ariquemes ela toma o "
        "Campus inteiro: laboratório de informática, unidades de produção "
        "agropecuária, cozinha-escola, sala de aula e pátio viram espaço de visita.\n"
        "\n"
        "Nesta edição, o tema **Ciência Delas** dá espaço às trajetórias de "
        "mulheres na ciência e na tecnologia ao longo de toda a programação."
    ),
    "cronograma_texto": (
        "Todas as atividades da semana, dia por dia, com horário e local. Esta "
        "página é atualizada pelas coordenações."
    ),
    "trabalhos_texto": (
        "Estudantes de qualquer curso podem inscrever trabalhos na semana, em "
        "duas mostras. Cada uma tem o seu regulamento, as suas datas e o seu "
        "formulário: escolha a sua e leia os documentos dela antes de enviar."
    ),
    "descricao": (
        "23ª Semana Nacional de Ciência e Tecnologia do IFRO Campus Ariquemes, "
        "de 27 a 30 de outubro de 2026. Tema: Ciência Delas. Programação, "
        "eventos e inscrições."
    ),
    "rodape_credito": "Feito por Júlio Sabaini",
    "portal_url": "https://portal.ifro.edu.br/ariquemes",
}

DIAS = [
    ("27/10", "terça", "Feira das Profissões e Empreendedorismo"),
    (
        "28/10",
        "quarta",
        "Cerimônia de abertura, Palestra de abertura, Mostras Científica, "
        "Tecnológica, Empreendedora, Curricularização da Extensão e Mesa redonda",
    ),
    ("29 e 30/10", "quinta e sexta", "SIAAGRO, oficinas, demonstrações e visitações"),
]

PASSOS = [
    (
        "Escolha o evento",
        "Cada um dos sete eventos abaixo tem inscrição própria. Dá para se "
        "inscrever em mais de um.",
    ),
    (
        "Clique em “Inscreva-se”",
        "O botão do cartão leva direto ao formulário daquele evento no SUAP.",
    ),
    (
        "Ainda não tem botão?",
        "Onde estiver escrito **“Inscrições em breve”**, a inscrição daquele "
        "evento ainda não abriu.",
    ),
]

FICHA = [
    ("Para quem", "Comunidade escolar do Campus, estudantes de outras escolas e público externo"),
    ("Trabalhos", "Duas mostras, cada uma com regulamento e prazo próprios: [ver como enviar](#trabalhos)"),
    ("Inscrições", "Pelo SUAP, uma por evento. Veja [Como se inscrever](#inscrever)"),
    ("Contato", "[depesp.ariquemes@ifro.edu.br](mailto:depesp.ariquemes@ifro.edu.br)"),
]


def preenche(apps, schema_editor):
    Site = apps.get_model("eventos", "Site")
    site, criado = Site.objects.get_or_create(pk=1, defaults=SITE)
    if not criado:
        return  # já preenchido pelo painel: quem está no banco manda
    for i, (rotulo, dia, texto) in enumerate(DIAS):
        apps.get_model("eventos", "DiaDaProgramacao").objects.create(
            site=site, ordem=i, rotulo=rotulo, dia_da_semana=dia, texto=texto
        )
    for i, (titulo, texto) in enumerate(PASSOS):
        apps.get_model("eventos", "PassoDaInscricao").objects.create(
            site=site, ordem=i, titulo=titulo, texto=texto
        )
    for i, (rotulo, texto) in enumerate(FICHA):
        apps.get_model("eventos", "ItemDaFicha").objects.create(
            site=site, ordem=i, rotulo=rotulo, texto=texto
        )


def apaga(apps, schema_editor):
    apps.get_model("eventos", "Site").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("eventos", "0017_textos_do_site"),
    ]

    operations = [
        migrations.RunPython(preenche, apaga),
    ]
