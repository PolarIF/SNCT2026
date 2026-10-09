from functools import wraps

from django.contrib import messages
from django.db import connection
from django.db.models import Prefetch
from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import (
    AnexoForm,
    CartaoForm,
    EtapaFormSet,
    EventoForm,
    HorarioFormSet,
    InscricaoDaAreaForm,
    LinkDeEnvioFormSet,
    SubmissaoForm,
)
from .models import (
    Anexo,
    Area,
    Cartao,
    Evento,
    Horario,
    Submissao,
    agenda_por_dia,
    areas_do_usuario,
)

# ---------------------------------------------------------------- site público


def home(request):
    # Nada aqui é HTML fixo: os cartões e o estado de cada inscrição vêm do
    # banco, para a organização mudar o site sem reimplantá-lo.
    cartoes = (
        Cartao.objects.filter(publicado=True, area__ativo=True)
        .select_related("area")
    )
    return render(
        request,
        "index.html",
        {
            "cartoes": cartoes,
            # Uma por mostra. O cartão de cada uma decide sozinho se oferece
            # o regulamento: só quando já há documento para ler ou baixar.
            "mostras": Submissao.objects.prefetch_related("links"),
        },
    )


def trabalhos(request):
    """Página da submissão: as mostras, cada uma com o que ler, as datas e o
    envio.

    Existe separada da página inicial porque o que ela carrega — regulamento,
    modelo de resumo, edital — é documento para baixar e ler com calma, e não
    cabia num cartão da home. As mostras ficam todas aqui, uma abaixo da
    outra, porque /trabalhos/ é o endereço que já foi divulgado.
    """
    mostras = Submissao.objects.prefetch_related(
        "links",
        "etapas",
        Prefetch("anexos", queryset=Anexo.objects.publicados(), to_attr="documentos"),
    )
    return render(
        request,
        "trabalhos.html",
        {"mostras": mostras, "pagina": "trabalhos"},
    )


def documento(request, slug):
    """Um documento lido no próprio site, sem baixar nada.

    É o caso do regulamento: ele não muda durante a semana, e ter de abrir um
    PDF no celular para conferir uma regra é atrito à toa. O PDF continua lá,
    na página de submissão — esta é a mesma coisa em HTML.
    """
    anexo = get_object_or_404(
        Anexo.objects.publicados().select_related("submissao"), slug=slug
    )
    if not anexo.tem_pagina:
        # Sem texto não há página: o documento existe só como arquivo.
        raise Http404
    return render(request, "documento.html", {"anexo": anexo, "pagina": "trabalhos"})


def saude(request):
    """Diz se a aplicação está de pé e enxergando o banco.

    É o que o healthcheck do container consulta, e o primeiro lugar onde a TI
    olha quando algo parece fora do ar. Responde texto puro de propósito.
    """
    try:
        connection.ensure_connection()
    except Exception as erro:  # noqa: BLE001 — qualquer falha aqui é "fora do ar"
        return HttpResponse(f"banco inacessível: {erro}\n", status=503, content_type="text/plain")
    return HttpResponse("ok\n", content_type="text/plain")


def cronograma(request):
    """Cronograma público: todos os eventos, agrupados por dia no template.

    O filtro por área é opcional e vem pela query string (?area=slug).
    """
    # Percorre Horario, e não Evento: é o horário que tem dia, e é por dia que
    # o cronograma se organiza. Um evento que acontece em dois dias aparece nos
    # dois; duas sessões no mesmo dia viram um cartão só (ver agenda_por_dia).
    horarios = Horario.objects.publicos()

    # Os atalhos oferecem só as áreas que já têm alguma atividade — filtro
    # vazio não serve de nada.
    areas = list(
        Area.objects.filter(ativo=True, eventos__horarios__isnull=False).distinct()
    )

    # O slug pedido, porém, é resolvido entre todas as áreas ativas. Os cartões
    # da página inicial apontam para cá antes de a área ter evento cadastrado;
    # nesse caso o certo é dizer "ainda não tem atividade nessa área", e não
    # mostrar o cronograma inteiro como se o filtro não existisse.
    slug = request.GET.get("area") or ""
    area_atual = None
    if slug:
        area_atual = Area.objects.filter(ativo=True, slug=slug).first()
        if area_atual:
            horarios = horarios.filter(evento__area=area_atual)
            if area_atual not in areas:
                areas.append(area_atual)
                areas.sort(key=lambda a: a.nome)

    dias = agenda_por_dia(horarios)

    return render(
        request,
        "cronograma.html",
        {
            "dias": dias,
            "areas": areas,
            "area_atual": area_atual,
            # O total conta atividades, e não horários: um evento que se repete
            # é uma atividade só na frase "N atividades". Como ele pode cair em
            # dias diferentes, soma-se item por item dos dias.
            "total": sum(len(dia["itens"]) for dia in dias),
            "pagina": "cronograma",
        },
    )


# --------------------------------------------------------- painel da coordenação


def _evento_do_usuario(request, pk):
    """Busca o evento restringindo às áreas do usuário.

    Pedir um evento de outra área devolve 404 — a checagem está aqui, no
    servidor, e não em esconder o botão de editar na tela.
    """
    return get_object_or_404(Evento, pk=pk, area__in=areas_do_usuario(request.user))


@login_required
def lista(request):
    areas = areas_do_usuario(request.user)
    # Mesma lógica do cronograma público: a agenda se organiza por horário, e
    # um evento repetido aparece em cada dia em que acontece.
    dias = agenda_por_dia(
        Horario.objects.filter(evento__area__in=areas).select_related(
            "evento", "evento__area"
        )
    )

    return render(
        request,
        "painel/lista.html",
        {
            "dias": dias,
            "total": sum(len(dia["itens"]) for dia in dias),
            # Evento sem nenhum horário não entra em `dias` e sumiria do painel
            # — e some justamente de quem precisa consertá-lo. Aparece à parte.
            "sem_horario": Evento.objects.filter(
                area__in=areas, horarios__isnull=True
            ).select_related("area"),
            "areas": areas,
            "varias_areas": len(areas) > 1,
            "hoje": timezone.localdate(),
            # Só o superusuário mexe na submissão; para os demais o bloco nem
            # aparece — e a view de /painel/submissao/ recusa do mesmo jeito.
            "mostras": (
                Submissao.objects.prefetch_related("links")
                if request.user.is_superuser
                else None
            ),
        },
    )


@login_required
def inscricao(request, slug):
    """Abre, fecha e troca o link de inscrição de um curso/área.

    A permissão é a mesma dos eventos: buscar pela queryset de
    areas_do_usuario faz uma área alheia devolver 404, tanto no GET quanto
    no POST.
    """
    area = get_object_or_404(areas_do_usuario(request.user), slug=slug)

    if request.method == "POST":
        form = InscricaoDaAreaForm(request.POST, instance=area)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Inscrições de {area.nome}: o site passa a mostrar {area.situacao_inscricao}.",
            )
            return redirect("painel:lista")
    else:
        form = InscricaoDaAreaForm(instance=area)

    return render(request, "painel/inscricao.html", {"form": form, "area": area})


def so_administrador(view):
    """Fecha a view para quem não é administrador.

    Devolve 404, e não 403, pela mesma razão do resto do painel: quem não
    pode mexer não precisa saber que a página existe. Vale no GET e no POST,
    porque é o decorador que barra — não o template que esconde o botão.
    """

    @wraps(view)
    @login_required
    def porteiro(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404
        return view(request, *args, **kwargs)

    return porteiro


@so_administrador
def submissao(request, slug):
    """Abre, fecha e troca os links e as datas da submissão de uma mostra.

    A submissão vale para a semana inteira — não é de uma coordenação, e sim
    da organização.
    """
    submissao = get_object_or_404(Submissao, slug=slug)

    if request.method == "POST":
        form = SubmissaoForm(request.POST, instance=submissao)
        links = LinkDeEnvioFormSet(request.POST, instance=submissao, prefix="links")
        etapas = EtapaFormSet(request.POST, instance=submissao, prefix="etapas")
        # Os três válidos antes de qualquer save, como no evento: gravar a
        # mostra e só depois descobrir um link inválido deixaria meio feito.
        if form.is_valid() and links.is_valid() and etapas.is_valid():
            form.save()
            links.save()
            etapas.save()
            # Relê do banco: `situacao` olha os links, e os da memória são os
            # de antes do save.
            submissao = Submissao.objects.get(pk=submissao.pk)
            messages.success(
                request,
                f"{submissao.nome}: o site passa a mostrar {submissao.situacao}.",
            )
            return redirect("painel:lista")
    else:
        form = SubmissaoForm(instance=submissao)
        links = LinkDeEnvioFormSet(instance=submissao, prefix="links")
        etapas = EtapaFormSet(instance=submissao, prefix="etapas")

    return render(
        request,
        "painel/submissao.html",
        {"form": form, "links": links, "etapas": etapas, "submissao": submissao},
    )


# ------------------------------------------- cartões da página inicial


@so_administrador
def cartoes(request):
    return render(
        request,
        "painel/cartoes.html",
        {"cartoes": Cartao.objects.select_related("area")},
    )


@so_administrador
def cartao_novo(request):
    if request.method == "POST":
        form = CartaoForm(request.POST)
        if form.is_valid():
            cartao = form.save()
            messages.success(request, f"Cartão “{cartao.titulo}” criado.")
            return redirect("painel:cartoes")
    else:
        # o novo entra no fim da fila, e não empatado com o primeiro
        ultimo = Cartao.objects.order_by("-ordem").first()
        form = CartaoForm(initial={"ordem": (ultimo.ordem + 1) if ultimo else 0})

    return render(
        request,
        "painel/cartao_form.html",
        {"form": form, "titulo_pagina": "Novo cartão"},
    )


@so_administrador
def cartao_editar(request, pk):
    cartao = get_object_or_404(Cartao, pk=pk)

    if request.method == "POST":
        form = CartaoForm(request.POST, instance=cartao)
        if form.is_valid():
            form.save()
            messages.success(request, f"Cartão “{cartao.titulo}” atualizado.")
            return redirect("painel:cartoes")
    else:
        form = CartaoForm(instance=cartao)

    return render(
        request,
        "painel/cartao_form.html",
        {"form": form, "cartao": cartao, "titulo_pagina": "Editar cartão"},
    )


@so_administrador
@require_http_methods(["GET", "POST"])
def cartao_excluir(request, pk):
    cartao = get_object_or_404(Cartao, pk=pk)

    # GET mostra a confirmação; só o POST apaga de verdade.
    if request.method == "POST":
        titulo = cartao.titulo
        cartao.delete()
        messages.success(request, f"Cartão “{titulo}” excluído.")
        return redirect("painel:cartoes")

    return render(request, "painel/cartao_excluir.html", {"cartao": cartao})


# ------------------------------------------- documentos da submissão


@so_administrador
def anexos(request):
    # Agrupados por mostra: cada uma tem o seu regulamento, e dois
    # "Regulamento" numa lista só não diriam qual é qual.
    return render(
        request,
        "painel/anexos.html",
        {"mostras": Submissao.objects.prefetch_related("anexos")},
    )


@so_administrador
def anexo_novo(request):
    if request.method == "POST":
        # request.FILES junto: sem ele o arquivo enviado não chega ao form.
        form = AnexoForm(request.POST, request.FILES)
        if form.is_valid():
            anexo = form.save()
            messages.success(request, f"Documento “{anexo.titulo}” publicado.")
            return redirect("painel:anexos")
    else:
        # O "+ Adicionar" de cada mostra já diz de qual mostra é o documento.
        mostra = Submissao.objects.filter(slug=request.GET.get("mostra", "")).first()
        # o novo entra no fim da fila da mostra, e não empatado com o primeiro
        ultimo = Anexo.objects.filter(submissao=mostra).order_by("-ordem").first()
        form = AnexoForm(
            initial={"submissao": mostra, "ordem": (ultimo.ordem + 1) if ultimo else 0}
        )

    return render(
        request,
        "painel/anexo_form.html",
        {"form": form, "titulo_pagina": "Novo documento"},
    )


@so_administrador
def anexo_editar(request, pk):
    anexo = get_object_or_404(Anexo, pk=pk)

    if request.method == "POST":
        form = AnexoForm(request.POST, request.FILES, instance=anexo)
        if form.is_valid():
            form.save()
            messages.success(request, f"Documento “{anexo.titulo}” atualizado.")
            return redirect("painel:anexos")
    else:
        form = AnexoForm(instance=anexo)

    return render(
        request,
        "painel/anexo_form.html",
        {"form": form, "anexo": anexo, "titulo_pagina": "Editar documento"},
    )


@so_administrador
@require_http_methods(["GET", "POST"])
def anexo_excluir(request, pk):
    anexo = get_object_or_404(Anexo, pk=pk)

    # GET mostra a confirmação; só o POST apaga de verdade.
    if request.method == "POST":
        titulo = anexo.titulo
        # O Django não apaga o arquivo junto com a linha. Aqui apaga, senão o
        # volume vai acumulando PDF que ninguém mais alcança.
        if anexo.arquivo:
            anexo.arquivo.delete(save=False)
        anexo.delete()
        messages.success(request, f"Documento “{titulo}” excluído.")
        return redirect("painel:anexos")

    return render(request, "painel/anexo_excluir.html", {"anexo": anexo})


@login_required
def novo(request):
    areas = areas_do_usuario(request.user)
    if not areas:
        return render(request, "painel/sem_area.html")

    if request.method == "POST":
        form = EventoForm(request.POST, user=request.user)
        horarios = HorarioFormSet(request.POST)
        # Os dois precisam estar válidos antes de qualquer save: gravar o
        # evento e só então descobrir que os horários não prestam deixaria no
        # banco um evento que não aparece em lugar nenhum do site.
        if form.is_valid() and horarios.is_valid():
            evento = form.save(commit=False)
            evento.criado_por = request.user
            evento.save()
            horarios.instance = evento
            horarios.save()
            messages.success(request, f"Evento “{evento.titulo}” cadastrado.")
            return redirect("painel:lista")
    else:
        form = EventoForm(user=request.user)
        horarios = HorarioFormSet()

    return render(
        request,
        "painel/form.html",
        {"form": form, "horarios": horarios, "titulo_pagina": "Novo evento"},
    )


@login_required
def editar(request, pk):
    evento = _evento_do_usuario(request, pk)

    if request.method == "POST":
        form = EventoForm(request.POST, instance=evento, user=request.user)
        horarios = HorarioFormSet(request.POST, instance=evento)
        if form.is_valid() and horarios.is_valid():
            form.save()
            horarios.save()
            messages.success(request, f"Evento “{evento.titulo}” atualizado.")
            return redirect("painel:lista")
    else:
        form = EventoForm(instance=evento, user=request.user)
        horarios = HorarioFormSet(instance=evento)

    return render(
        request,
        "painel/form.html",
        {
            "form": form,
            "horarios": horarios,
            "evento": evento,
            "titulo_pagina": "Editar evento",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def excluir(request, pk):
    evento = _evento_do_usuario(request, pk)

    # GET mostra a confirmação; só o POST apaga de verdade.
    if request.method == "POST":
        titulo = evento.titulo
        evento.delete()
        messages.success(request, f"Evento “{titulo}” excluído.")
        return redirect("painel:lista")

    return render(request, "painel/excluir.html", {"evento": evento})
