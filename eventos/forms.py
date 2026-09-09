from django import forms

from .models import Evento, areas_do_usuario


class EventoForm(forms.ModelForm):
    """Formulário de evento do painel.

    A lista de áreas é reduzida às áreas do usuário no __init__. Isso não é
    só cosmético: é essa mesma queryset que o Django usa para validar o POST,
    então um envio manual com o id de outra área é recusado.
    """

    class Meta:
        model = Evento
        fields = ["titulo", "area", "data", "hora_inicio", "hora_fim", "local", "descricao"]
        widgets = {
            # type="date" e type="time" fazem o navegador (e o celular) abrirem
            # o seletor nativo; o format é o que o input espera receber de volta.
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
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
