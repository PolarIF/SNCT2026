import re

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()

# [texto](endereço). O endereço só pode ser de site (http/https), de e-mail,
# um caminho do próprio site ou uma âncora: "javascript:" e companhia não
# casam com o padrão e ficam como texto. Aspas e < > não entram no endereço,
# e o texto já chegou escapado — não há como sair do atributo href.
LINK = re.compile(r"\[([^\]]+)\]\(((?:https?://|mailto:|/|#)[^\s()\"<>]*)\)")


def _links(escapado):
    def troca(m):
        texto, url = m.group(1), m.group(2)
        fora = url.startswith(("http://", "https://"))
        alvo = ' target="_blank" rel="noopener"' if fora else ""
        return f'<a href="{url}"{alvo}>{texto}</a>'

    return LINK.sub(troca, escapado)


def _em_linha(escapado):
    """O que vale dentro de uma linha: Campus em itálico, negrito e link."""
    escapado = re.sub(r"\bCampus\b", "<i>Campus</i>", escapado)
    # O negrito chegou com o texto das mostras, que destaca o que não pode
    # passar batido ("modalidade banner"). Vem depois do escape, como o
    # resto: os asteriscos não carregam HTML nenhum.
    escapado = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escapado)
    return _links(escapado)


@register.filter(needs_autoescape=True)
def em_linha(texto, autoescape=True):
    """A marcação de texto_rico sem parágrafos: para um título, um item de
    ficha, uma linha só. **negrito**, [link](endereço) e *Campus*."""
    escapar = conditional_escape if autoescape else (lambda x: x)
    return mark_safe(_em_linha(escapar(texto or "")))


@register.filter(needs_autoescape=True)
def campus(texto, autoescape=True):
    """Põe *Campus* em itálico, como manda a convenção do IFRO.

    O texto vem do banco e é escapado normalmente aqui; só a palavra Campus
    vira marcação. Assim ninguém precisa digitar HTML no painel para manter a
    grafia certa — e nenhum HTML digitado lá chega ao site.
    """
    escapar = conditional_escape if autoescape else (lambda x: x)
    return mark_safe(re.sub(r"\bCampus\b", "<i>Campus</i>", escapar(texto or "")))


@register.filter(needs_autoescape=True)
def texto_rico(texto, autoescape=True):
    """Transforma o texto digitado no painel em HTML — e só nesta marcação.

    O regulamento é texto longo: precisa de título, parágrafo e lista, e não
    dá para pedir que a organização digite HTML. A convenção é a menor
    possível:

        ## Título           vira <h2>
        - item              vira item de lista
        **texto**           vira negrito
        [texto](endereço)   vira link
        linha em branco     separa parágrafos

    Linhas seguidas viram um parágrafo só, e não um por linha: quem escreve
    num textarea quebra a linha onde a janela acaba, sem querer dizer nada
    com isso.

    Tudo é escapado antes de qualquer coisa, e só estas cinco formas viram
    marcação: um `<script>` digitado no painel aparece como texto na tela.
    """
    escapar = conditional_escape if autoescape else (lambda x: x)
    partes = []
    paragrafo = []
    lista = []

    def fecha_o_paragrafo():
        if paragrafo:
            partes.append(f"<p>{' '.join(paragrafo)}</p>")
            paragrafo.clear()

    def fecha_a_lista():
        if lista:
            itens = "".join(f"<li>{item}</li>" for item in lista)
            partes.append(f"<ul>{itens}</ul>")
            lista.clear()

    for linha in (texto or "").strip().splitlines():
        linha = linha.strip()
        if not linha:
            fecha_o_paragrafo()
            fecha_a_lista()
            continue

        escapada = _em_linha(escapar(linha))
        if linha.startswith("## "):
            fecha_o_paragrafo()
            fecha_a_lista()
            partes.append(f"<h2>{escapada[3:].strip()}</h2>")
        elif linha.startswith("- "):
            fecha_o_paragrafo()
            lista.append(escapada[2:].strip())
        else:
            fecha_a_lista()
            paragrafo.append(escapada)

    fecha_o_paragrafo()
    fecha_a_lista()
    return mark_safe("".join(partes))
