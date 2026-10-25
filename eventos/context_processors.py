from .models import Site, Submissao


def site(request):
    """Os textos do site em todo template, como `site`.

    É uma consulta por página — uma linha só, pela chave. O cabeçalho, o
    rodapé e as meta tags estão em base.html, que todas as páginas públicas
    estendem, então não há como poupar a consulta sem espalhar o `site` por
    cada view.
    """
    return {"site": Site.atual()}


def painel(request):
    """As mostras, para o menu lateral do administrador no painel.

    Só consulta no /painel/ e só para o superusuário: é o único lugar onde o
    menu existe, e as páginas públicas não precisam pagar por ele.
    """
    user = getattr(request, "user", None)
    if not request.path.startswith("/painel/") or not (user and user.is_superuser):
        return {}
    return {"painel_mostras": Submissao.objects.only("nome", "slug")}
