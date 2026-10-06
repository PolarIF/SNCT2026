from django import forms
from django.conf import settings

from .models import (
    Anexo,
    Area,
    Cartao,
    Evento,
    Horario,
    Submissao,
    areas_do_usuario,
)


class EventoForm(forms.ModelForm):
    """Formulário de evento do painel.

    A lista de áreas é reduzida às áreas do usuário no __init__. Isso não é
    só cosmético: é essa mesma queryset que o Django usa para validar o POST,
    então um envio manual com o id de outra área é recusado.
    """

    link_inscricao = forms.URLField(
        label="Link de inscrição desta atividade",
        required=False,
        # Sem isso, colar o endereço sem o "https://" viraria http.
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://suap.ifro.edu.br/..."}),
        help_text="Só quando esta atividade tem inscrição separada. Em branco, "
        "o cronograma usa o link do curso/área.",
    )

    class Meta:
        model = Evento
        # Os dias e horários saíram daqui: viraram o formset abaixo, porque um
        # evento pode ter mais de um.
        fields = [
            "titulo",
            "area",
            "local",
            "descricao",
            "link_inscricao",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"placeholder": "Ex.: Palestra sobre Inteligência Artificial"}),
            "local": forms.TextInput(attrs={"placeholder": "Ex.: Auditório"}),
            "descricao": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        areas = areas_do_usuario(user)
        campo_area = self.fields["area"]
        campo_area.queryset = areas

        # Quem cuida de uma única área não precisa escolher nada: o campo vira
        # oculto e o template mostra o nome da área como texto.
        self.area_unica = areas[0] if len(areas) == 1 else None
        if self.area_unica:
            campo_area.initial = self.area_unica
            campo_area.widget = forms.HiddenInput()
        else:
            campo_area.empty_label = "Escolha o curso/área"


class HorarioForm(forms.ModelForm):
    """Uma linha de "quando" dentro do formulário do evento."""

    class Meta:
        model = Horario
        fields = ["data", "hora_inicio", "hora_fim"]
        # Curtos porque os três ficam lado a lado numa linha só: rótulos longos
        # quebravam em duas linhas e desalinhavam os campos.
        labels = {"data": "Dia", "hora_inicio": "Início", "hora_fim": "Término"}
        widgets = {
            # type="date" e type="time" fazem o navegador (e o celular) abrirem
            # o seletor nativo; o format é o que o input espera receber de volta.
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }


class HorarioFormSetBase(forms.BaseInlineFormSet):
    """O formset dos dias e horários de um evento.

    Faz duas coisas que o formset padrão não faz: exige pelo menos um horário
    sobrevivente e recusa dois horários iguais no mesmo envio.
    """

    def clean(self):
        # As checagens próprias vêm antes de super(): o validate_unique do
        # Django enxerga a mesma duplicidade (há UniqueConstraint no banco),
        # mas avisa com "corrija o valor duplicado para data e hora_inicio" —
        # nome de coluna, não português. Quem chega primeiro escreve a
        # mensagem, então vem primeiro quem sabe explicar.
        if any(self.errors):
            return

        vistos = set()
        sobreviventes = 0
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            sobreviventes += 1
            chave = (form.cleaned_data["data"], form.cleaned_data["hora_inicio"])
            if chave in vistos:
                # A mesma checagem existe como UniqueConstraint no banco. Aqui
                # ela vira mensagem em vez de erro 500: o banco só veria isto
                # depois do save, e aí já seria tarde para explicar.
                raise forms.ValidationError(
                    "Há dois horários iguais: mesmo dia e mesma hora de início."
                )
            vistos.add(chave)

        if not sobreviventes:
            raise forms.ValidationError(
                "O evento precisa de pelo menos um dia e horário."
            )

        super().clean()


HorarioFormSet = forms.inlineformset_factory(
    Evento,
    Horario,
    form=HorarioForm,
    formset=HorarioFormSetBase,
    # Uma linha vazia sobrando: dá para acrescentar um horário sem depender de
    # JavaScript. O botão "adicionar" clona esta linha quando há JS.
    extra=1,
    can_delete=True,
)


class InscricaoDaAreaForm(forms.ModelForm):
    """Os dois campos da inscrição, para a coordenação mexer pelo painel.

    Quem pode mexer em qual área é decidido na view, não aqui: este formulário
    sempre recebe uma área que já passou pela checagem de permissão.
    """

    link_inscricao = forms.URLField(
        label="Link de inscrição",
        required=False,
        # Sem isso, colar "suap.ifro.edu.br/..." sem o "https://" viraria http.
        assume_scheme="https",
        widget=forms.URLInput(
            attrs={"placeholder": "https://suap.ifro.edu.br/eventos/inscricao/1/0000/"}
        ),
        help_text="Cole aqui o endereço da inscrição no SUAP.",
    )

    class Meta:
        model = Area
        fields = ["inscricoes_abertas", "link_inscricao"]
        labels = {"inscricoes_abertas": "Inscrições abertas"}
        help_texts = {
            "inscricoes_abertas": "Desmarcado, o site mostra “Inscrições em breve”.",
        }


class SubmissaoForm(forms.ModelForm):
    """Submissão de trabalhos, no painel.

    Quem pode mexer é decidido na view: a submissão é uma só para o evento
    inteiro, então ela é da organização, não de uma coordenação.
    """

    link = forms.URLField(
        label="Link da submissão",
        required=False,
        # Sem isso, colar o endereço sem o "https://" viraria http.
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://forms.gle/..."}),
        help_text="Cole aqui o endereço do formulário de envio dos trabalhos.",
    )

    class Meta:
        model = Submissao
        fields = ["aberta", "link", "prazo"]
        labels = {"aberta": "Submissão aberta", "prazo": "Prazo de envio"}
        help_texts = {
            "aberta": "Desmarcada, o site mostra “A submissão abre em breve”.",
            "prazo": "Opcional. Em branco, a página não fala em prazo.",
        }
        widgets = {
            # type="date" abre o seletor nativo, inclusive no celular.
            "prazo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }


class CartaoForm(forms.ModelForm):
    """Um cartão da página inicial. Só o administrador chega aqui.

    O texto é gravado como texto puro: o template escapa tudo na hora de
    mostrar, então digitar HTML aqui não vira marcação no site.
    """

    class Meta:
        model = Cartao
        fields = [
            "titulo",
            "area",
            "trilha",
            "responsavel",
            "coordenacao",
            "descricao",
            "programacao_rotulo",
            "programacao",
            "link_horarios",
            "ordem",
            "publicado",
        ]
        widgets = {
            "titulo": forms.TextInput(
                attrs={"placeholder": "Ex.: Biologia — Oficinas e Demonstrações"}
            ),
            "trilha": forms.TextInput(attrs={"placeholder": "Ex.: Abertura oficial"}),
            "responsavel": forms.TextInput(attrs={"placeholder": "Nome do professor"}),
            "coordenacao": forms.TextInput(
                attrs={"placeholder": "Ex.: Coordenação de Biologia"}
            ),
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "programacao_rotulo": forms.TextInput(attrs={"placeholder": "29 e 30/10"}),
            "programacao": forms.Textarea(
                attrs={"rows": 6, "placeholder": "Oficinas práticas\nDemonstrações\nVisitações"}
            ),
            "link_horarios": forms.URLInput(
                attrs={"placeholder": "https://exemplo.github.io/pagina-do-curso/"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = Area.objects.filter(ativo=True)
        self.fields["area"].empty_label = "Escolha o curso/área"


class AnexoForm(forms.ModelForm):
    """Um documento da página de submissão. Só o administrador chega aqui."""

    link = forms.URLField(
        label="Link",
        required=False,
        # Sem isso, colar o endereço sem o "https://" viraria http.
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://drive.google.com/..."}),
        help_text="Para um documento que já está publicado em outro lugar. "
        "Deixe em branco se enviou um arquivo.",
    )

    class Meta:
        model = Anexo
        fields = ["titulo", "descricao", "arquivo", "link", "texto", "ordem", "publicado"]
        widgets = {
            "titulo": forms.TextInput(attrs={"placeholder": "Ex.: Regulamento"}),
            "descricao": forms.TextInput(
                attrs={"placeholder": "Ex.: Regras de formatação e critérios de avaliação"}
            ),
            "texto": forms.Textarea(
                attrs={
                    "rows": 16,
                    "placeholder": "## Das disposições gerais\n\n"
                    "Escreva aqui o texto do documento.\n\n"
                    "- um item de lista\n- outro item",
                }
            ),
        }

    def clean_arquivo(self):
        arquivo = self.cleaned_data.get("arquivo")
        # `size` só existe no arquivo recém-enviado; no que já está gravado o
        # campo volta como FieldFile e não há nada para conferir.
        tamanho = getattr(arquivo, "size", None)
        if tamanho and tamanho > settings.TAMANHO_MAXIMO_ANEXO:
            limite = settings.TAMANHO_MAXIMO_ANEXO // (1024 * 1024)
            raise forms.ValidationError(
                f"O arquivo tem {tamanho / (1024 * 1024):.1f} MB e o limite é "
                f"{limite} MB. Comprima o PDF ou publique em outro lugar e use o link."
            )
        return arquivo
