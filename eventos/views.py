from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import EventoForm
from .models import Area, Evento, areas_do_usuario

# ---------------------------------------------------------------- site público


def home(request):
    return render(request, "index.html")


def cronograma(request):
    """Cronograma público: todos os eventos, agrupados por dia no template.

    O filtro por área é opcional e vem pela query string (?area=slug).
    """
    eventos = Evento.objects.publicos()

    areas = Area.objects.filter(ativo=True, eventos__isnull=False).distinct()

    slug = request.GET.get("area") or ""
    area_atual = None
    if slug:
        area_atual = areas.filter(slug=slug).first()
        if area_atual:
            eventos = eventos.filter(area=area_atual)

    return render(
        request,
        "cronograma.html",
        {
            "eventos": eventos,
            "areas": areas,
            "area_atual": area_atual,
            "total": eventos.count(),
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
    eventos = (
        Evento.objects.filter(area__in=areas)
        .select_related("area")
        .order_by("data", "hora_inicio", "titulo")
    )

    return render(
        request,
        "painel/lista.html",
        {
            "eventos": eventos,
            "areas": areas,
            "varias_areas": len(areas) > 1,
            "hoje": timezone.localdate(),
        },
    )


@login_required
def novo(request):
    areas = areas_do_usuario(request.user)
    if not areas:
        return render(request, "painel/sem_area.html")

    if request.method == "POST":
        form = EventoForm(request.POST, user=request.user)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.criado_por = request.user
            evento.save()
            messages.success(request, f"Evento “{evento.titulo}” cadastrado.")
            return redirect("painel:lista")
    else:
        form = EventoForm(user=request.user)

    return render(request, "painel/form.html", {"form": form, "titulo_pagina": "Novo evento"})


@login_required
def editar(request, pk):
    evento = _evento_do_usuario(request, pk)

    if request.method == "POST":
        form = EventoForm(request.POST, instance=evento, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f"Evento “{evento.titulo}” atualizado.")
            return redirect("painel:lista")
    else:
        form = EventoForm(instance=evento, user=request.user)

    return render(
        request,
        "painel/form.html",
        {"form": form, "evento": evento, "titulo_pagina": "Editar evento"},
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
