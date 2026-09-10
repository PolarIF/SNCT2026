from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as UserAdminPadrao
from django.contrib.auth.forms import UserChangeForm as UserChangeFormPadrao
from django.contrib.auth.forms import UserCreationForm as UserCreationFormPadrao
from django.contrib.auth.models import Group, User

from .models import Area, Evento


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    # "inscrições abertas" é editável direto na lista: dá para abrir e fechar
    # as sete áreas numa tela só, que é o que a organização faz na semana.
    list_display = [
        "nome",
        "inscricoes_abertas",
        "situacao_da_inscricao",
        "ativo",
        "quantos_eventos",
        "quem_administra",
    ]
    list_editable = ["inscricoes_abertas"]
    list_filter = ["inscricoes_abertas", "ativo"]
    search_fields = ["nome"]
    prepopulated_fields = {"slug": ["nome"]}
    filter_horizontal = ["gestores"]

    fieldsets = (
        (None, {"fields": ("nome", "slug", "ativo")}),
        (
            "Inscrição",
            {
                "fields": ("inscricoes_abertas", "link_inscricao"),
                "description": "É isso que a página inicial mostra no cartão "
                "deste curso/área. Sem link não aparece botão, mesmo com a "
                "caixa marcada.",
            },
        ),
        ("Quem administra", {"fields": ("gestores",)}),
    )

    @admin.display(description="o que aparece no site")
    def situacao_da_inscricao(self, area):
        return area.situacao_inscricao

    @admin.display(description="eventos")
    def quantos_eventos(self, area):
        return area.eventos.count()

    @admin.display(description="quem administra")
    def quem_administra(self, area):
        nomes = [u.get_full_name() or u.username for u in area.gestores.all()]
        return ", ".join(nomes) or "—"


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ["titulo", "area", "data", "hora_inicio", "local"]
    list_filter = ["area", "data"]
    search_fields = ["titulo", "descricao", "local"]
    date_hierarchy = "data"
    autocomplete_fields = ["area"]
    readonly_fields = ["criado_por", "criado_em", "atualizado_em"]

    def save_model(self, request, obj, form, change):
        if not change and not obj.criado_por:
            obj.criado_por = request.user
        super().save_model(request, obj, form, change)


# --------------------------------------------------------------------------
# Usuários: o mesmo UserAdmin do Django, com um campo a mais para escolher as
# áreas. A relação vive em Area.gestores, então dá para editar pelos dois
# lados — pela área ou pela conta.
# --------------------------------------------------------------------------


def campo_areas():
    """O campo extra de áreas, igual nos dois formulários (criar e editar)."""
    return forms.ModelMultipleChoiceField(
        queryset=Area.objects.all(),
        required=False,
        label="Cursos/áreas que esta conta pode administrar",
        widget=admin.widgets.FilteredSelectMultiple("cursos/áreas", is_stacked=False),
        help_text="Um administrador principal (superusuário) administra todas, "
        "independentemente do que estiver marcado aqui.",
    )


class AreasNoUsuario:
    """Liga o campo `areas` à relação que vive em Area.gestores.

    Não é um Form: só carrega o valor inicial e grava depois do save. Os
    formulários abaixo é que declaram o campo, porque o Django só reconhece
    campos declarados na própria classe do formulário.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["areas"].initial = self.instance.areas_geridas.all()

    def _save_m2m(self):
        super()._save_m2m()
        self.instance.areas_geridas.set(self.cleaned_data.get("areas", []))


class UserChangeFormComAreas(AreasNoUsuario, UserChangeFormPadrao):
    areas = campo_areas()


class UserCreationFormComAreas(AreasNoUsuario, UserCreationFormPadrao):
    areas = campo_areas()


class UserAdmin(UserAdminPadrao):
    form = UserChangeFormComAreas
    add_form = UserCreationFormComAreas
    list_display = ["username", "get_full_name", "areas_resumo", "is_active", "is_superuser"]
    list_filter = ["is_active", "is_superuser", "areas_geridas"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Quem é", {"fields": ("first_name", "last_name", "email")}),
        ("Acesso", {"fields": ("is_active", "areas")}),
        (
            "Administração",
            {
                "classes": ("collapse",),
                "fields": ("is_superuser", "is_staff", "groups", "user_permissions"),
                "description": "Marque as duas primeiras apenas para outro "
                "administrador principal. Coordenações não usam esta área.",
            },
        ),
        ("Datas", {"classes": ("collapse",), "fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "fields": ("username", "password1", "password2"),
            },
        ),
        ("Quem é", {"fields": ("first_name", "last_name")}),
        ("Acesso", {"fields": ("areas",)}),
    )

    @admin.display(description="cursos/áreas")
    def areas_resumo(self, user):
        if user.is_superuser:
            return "todas (administrador)"
        nomes = [a.nome for a in user.areas_geridas.all()]
        return ", ".join(nomes) or "—"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Grupos não são usados: a permissão do painel vem das áreas.
admin.site.unregister(Group)
