from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as UserAdminPadrao
from django.contrib.auth.forms import UserChangeForm as UserChangeFormPadrao
from django.contrib.auth.forms import UserCreationForm as UserCreationFormPadrao
from django.contrib.auth.models import Group, User

from .models import Anexo, Area, Cartao, Etapa, Evento, Horario, LinkDeEnvio, Submissao


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


class LinkDeEnvioInline(admin.TabularInline):
    model = LinkDeEnvio
    extra = 1


class EtapaInline(admin.TabularInline):
    model = Etapa
    extra = 1


@admin.register(Submissao)
class SubmissaoAdmin(admin.ModelAdmin):
    """As mostras e a submissão de cada uma.

    O caminho normal é o painel (/painel/ → Submissão de trabalhos). Isto
    aqui existe para o caso de a organização já estar no /admin/ criando
    contas. Não se apaga mostra por aqui: os documentos dela são PROTECT, e
    tirar uma do ar é fechar a submissão.
    """

    list_display = ["nome", "aberta", "situacao_no_site", "prazo", "ordem"]
    prepopulated_fields = {"slug": ["nome"]}
    fields = ["nome", "slug", "resumo", "aberta", "prazo", "ordem"]
    inlines = [LinkDeEnvioInline, EtapaInline]

    @admin.display(description="o que aparece no site")
    def situacao_no_site(self, submissao):
        return submissao.situacao

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cartao)
class CartaoAdmin(admin.ModelAdmin):
    """Os cartões da página inicial.

    O caminho normal é /painel/cartoes/, que é mais simples de usar. Isto
    existe para quem já está aqui dentro.
    """

    list_display = ["titulo", "etiqueta_no_site", "area", "ordem", "publicado"]
    list_editable = ["ordem", "publicado"]
    list_filter = ["publicado", "area"]
    search_fields = ["titulo", "descricao", "responsavel"]
    autocomplete_fields = ["area"]

    fieldsets = (
        (None, {"fields": ("titulo", "area", "trilha")}),
        ("Quem responde", {"fields": ("responsavel", "coordenacao")}),
        ("Conteúdo", {"fields": ("descricao", "programacao_rotulo", "programacao")}),
        (
            "Horários",
            {
                "fields": ("link_horarios",),
                "description": "Em branco, o botão “Ver horários” leva ao "
                "cronograma do site.",
            },
        ),
        ("Na página", {"fields": ("ordem", "publicado")}),
    )

    @admin.display(description="etiqueta")
    def etiqueta_no_site(self, cartao):
        return cartao.etiqueta


class HorarioInline(admin.TabularInline):
    """Os dias e horários do evento, editados dentro dele.

    `min_num=1` porque evento sem horário não aparece em lugar nenhum do site:
    o cronograma percorre Horario, não Evento.
    """

    model = Horario
    extra = 1
    min_num = 1


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    # A data saiu de Evento e foi para Horario, então nem list_display nem
    # list_filter nem date_hierarchy podem mais apontar para ela. O que fica é
    # uma coluna que lê os horários já carregados pelo prefetch.
    list_display = ["titulo", "area", "quando", "local", "tem_inscricao_propria"]
    list_filter = ["area", "horarios__data"]
    search_fields = ["titulo", "descricao", "local"]
    autocomplete_fields = ["area"]
    readonly_fields = ["criado_por", "criado_em", "atualizado_em"]
    inlines = [HorarioInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("horarios")

    @admin.display(description="quando")
    def quando(self, obj):
        horarios = list(obj.horarios.all())
        if not horarios:
            return "—"
        return ", ".join(f"{h.data:%d/%m} {h.intervalo}" for h in horarios)

    @admin.display(description="inscrição própria", boolean=True)
    def tem_inscricao_propria(self, obj):
        return obj.inscricao_propria

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


@admin.register(Anexo)
class AnexoAdmin(admin.ModelAdmin):
    """Os documentos da página de submissão.

    O caminho normal é o painel (/painel/anexos/); isto aqui é a rede de
    segurança de quem já está no /admin/.
    """

    list_display = ["titulo", "submissao", "formato", "ordem", "publicado"]
    prepopulated_fields = {"slug": ["titulo"]}
    list_editable = ["ordem", "publicado"]
    list_filter = ["submissao", "publicado"]
    search_fields = ["titulo", "descricao"]

    fieldsets = (
        (None, {"fields": ("submissao", "titulo", "descricao")}),
        (
            "O documento",
            {
                "fields": ("arquivo", "link"),
                "description": "Um ou outro: ou o arquivo enviado, ou o "
                "endereço de um documento que já está publicado fora daqui. "
                "Os dois em branco deixam o documento como “em breve”.",
            },
        ),
        (
            "No site",
            {
                "fields": ("texto", "slug"),
                "description": "Preenchido, o documento também ganha página "
                "no site, em /trabalhos/&lt;endereço curto&gt;/.",
            },
        ),
        ("Na página", {"fields": ("ordem", "publicado")}),
    )

    @admin.display(description="formato")
    def formato(self, obj):
        return obj.formato
