from django import template

register = template.Library()


@register.filter
def por_slug(mapa, slug):
    """Pega um item do dicionário por uma chave com hífen.

    A sintaxe normal do template (`areas.informatica`) não alcança chaves como
    "agronomia-e-agropecuaria", então os cartões da página inicial usam
    `areas|por_slug:"agronomia-e-agropecuaria"`.
    """
    return (mapa or {}).get(slug)
