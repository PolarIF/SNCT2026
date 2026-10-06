from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Area(models.Model):
    """Curso ou área que tem eventos na semana.

    A área é também a unidade de permissão: uma conta de coordenação
    administra os eventos das áreas ligadas a ela em `gestores`.
    """

    nome = models.CharField("nome", max_length=80, unique=True)
    slug = models.SlugField(
        "endereço curto",
        max_length=80,
        unique=True,
        blank=True,
        help_text="Preenchido automaticamente a partir do nome.",
    )
    ativo = models.BooleanField(
        "ativo",
        default=True,
        help_text="Desmarque para esconder a área sem apagar os eventos dela.",
    )
    # Inscrição: é por área, e quem controla é a organização, pelo /admin/.
    # Ficam aqui e não no HTML porque mudam durante a semana e o site roda em
    # container — mexer no template exigiria reconstruir e reimplantar.
    inscricoes_abertas = models.BooleanField(
        "inscrições abertas",
        default=False,
        help_text="Desmarcado, a página mostra “Inscrições em breve”.",
    )
    link_inscricao = models.URLField(
        "link de inscrição",
        max_length=300,
        blank=True,
        help_text="Endereço da inscrição no SUAP. Sem ele não aparece botão, "
        "mesmo com as inscrições marcadas como abertas.",
    )

    gestores = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="quem pode administrar",
        related_name="areas_geridas",
        blank=True,
    )

    class Meta:
        verbose_name = "curso/área"
        verbose_name_plural = "cursos/áreas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)[:80]
        super().save(*args, **kwargs)

    @property
    def mostra_botao_inscricao(self):
        """Só há botão quando as inscrições estão abertas e há para onde ir."""
        return bool(self.inscricoes_abertas and self.link_inscricao)

    @property
    def situacao_inscricao(self):
        """O que o cartão desta área mostra hoje na página inicial.

        Fica no modelo porque o /admin/ e o painel dizem a mesma coisa, e
        dizer diferente seria pior que não dizer.
        """
        if self.mostra_botao_inscricao:
            return "botão “Inscreva-se”"
        if self.inscricoes_abertas:
            return "marcada como aberta, mas sem link — nenhum botão aparece"
        return "“Inscrições em breve”"


class EventoQuerySet(models.QuerySet):
    def publicos(self):
        """O que aparece no cronograma do site."""
        return self.filter(area__ativo=True).select_related("area")


class Evento(models.Model):
    titulo = models.CharField("título", max_length=160)
    descricao = models.TextField(
        "descrição",
        blank=True,
        help_text="Uma ou duas frases sobre a atividade.",
    )
    # Quando a atividade acontece não mora mais aqui: um evento pode ter mais
    # de um dia e horário, e cada um é uma linha em `horarios`.
    local = models.CharField("local", max_length=120, blank=True)
    link_inscricao = models.URLField(
        "link de inscrição",
        max_length=300,
        blank=True,
        help_text="Só quando esta atividade tem inscrição separada. Em branco, "
        "o cronograma usa o link do curso/área — o mesmo do cartão da página "
        "inicial.",
    )
    area = models.ForeignKey(
        Area,
        verbose_name="curso/área",
        on_delete=models.PROTECT,
        related_name="eventos",
    )

    criado_em = models.DateTimeField("cadastrado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("última alteração", auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cadastrado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_criados",
    )

    objects = EventoQuerySet.as_manager()

    class Meta:
        verbose_name = "evento"
        verbose_name_plural = "eventos"
        # Ordenar por data deixou de ser possível aqui: a data é de Horario, e
        # um evento pode ter várias. Quem precisa de ordem cronológica percorre
        # Horario, que é o que o cronograma e o painel fazem.
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo

    # Inscrição: o link próprio manda, e o da área é o padrão. Uma oficina
    # com vagas limitadas costuma ter formulário só dela; o resto da semana
    # usa a inscrição única do curso, que a coordenação já mantém na área.
    @property
    def url_inscricao(self):
        return self.link_inscricao or self.area.link_inscricao

    @property
    def mostra_botao_inscricao(self):
        """Quando o cronograma mostra o botão de inscrição deste evento.

        Link próprio aparece sempre: quem o colou aqui quis inscrição nesta
        atividade, e não faria sentido depender do interruptor da área. Sem
        link próprio, o botão é o da área e obedece ao interruptor dela.
        """
        if self.link_inscricao:
            return True
        return self.area.mostra_botao_inscricao

    @property
    def inscricao_propria(self):
        """O botão leva a um formulário só desta atividade?"""
        return bool(self.link_inscricao)

    def horarios_em(self, data):
        """Os horários deste evento num dia. Avalia em Python de propósito:
        quem chama já trouxe `horarios` com prefetch, e uma consulta por dia
        desfaria isso."""
        return [h for h in self.horarios.all() if h.data == data]


class HorarioQuerySet(models.QuerySet):
    def publicos(self):
        """O que aparece no cronograma do site.

        Traz evento e área junto: o cronograma lê título, local e inscrição de
        cada um, e sem isto seriam duas consultas por linha da agenda.
        """
        return self.filter(evento__area__ativo=True).select_related(
            "evento", "evento__area"
        )


class Horario(models.Model):
    """Um dia e horário em que o evento acontece.

    Era um trio de campos dentro de Evento (data, hora_inicio, hora_fim), o
    que amarrava cada atividade a um único momento. Virou tabela porque a
    mesma atividade pode se repetir: uma oficina que roda de manhã e de tarde
    no mesmo dia, uma mostra que ocupa quinta e sexta.

    O que o site faz com isso está em `agenda_por_dia`: repetição no mesmo dia
    é um cartão só com os dois horários; dias diferentes são um cartão em cada
    dia, cada um com o horário daquele dia.
    """

    evento = models.ForeignKey(
        "Evento",
        verbose_name="evento",
        on_delete=models.CASCADE,
        related_name="horarios",
    )
    data = models.DateField("dia")
    hora_inicio = models.TimeField("horário de início")
    hora_fim = models.TimeField("horário de término", null=True, blank=True)

    objects = HorarioQuerySet.as_manager()

    class Meta:
        verbose_name = "dia e horário"
        verbose_name_plural = "dias e horários"
        ordering = ["data", "hora_inicio"]
        indexes = [models.Index(fields=["data", "hora_inicio"])]
        constraints = [
            # O mesmo evento no mesmo dia e na mesma hora é engano de digitação,
            # e apareceria duas vezes no cronograma. hora_fim fica fora da chave
            # de propósito: dois horários que começam juntos já são o engano,
            # terminem quando terminarem.
            models.UniqueConstraint(
                fields=["evento", "data", "hora_inicio"],
                name="horario_sem_repeticao",
            )
        ]

    def __str__(self):
        return f"{self.data:%d/%m} {self.intervalo}"

    def clean(self):
        if self.hora_fim and self.hora_inicio and self.hora_fim <= self.hora_inicio:
            raise ValidationError(
                {"hora_fim": "O horário de término tem que ser depois do de início."}
            )

    @property
    def intervalo(self):
        """"14:00 às 16:00", ou apenas "14:00" quando não há término."""
        inicio = self.hora_inicio.strftime("%H:%M")
        if not self.hora_fim:
            return inicio
        return f"{inicio} às {self.hora_fim:%H:%M}"


def agenda_por_dia(horarios):
    """Horários agrupados por dia e, dentro do dia, por evento.

    Devolve uma lista de {"data": date, "itens": [{"evento", "horarios"}]}.

    É aqui que mora a regra pedida: duas sessões no mesmo dia viram um item só
    com os dois horários, e sessões em dias diferentes viram um item em cada
    dia. Fazer isso em Python, e não com `regroup` no template, é o que
    permite agrupar por duas chaves de uma vez — dia e evento.

    `horarios` precisa vir ordenado por data e hora_inicio, que é a ordenação
    padrão de Horario. A ordem de chegada é a ordem de saída: dentro do dia,
    cada evento aparece na posição do seu primeiro horário.
    """
    dias = []
    indice_do_dia = {}
    for horario in horarios:
        dia = indice_do_dia.get(horario.data)
        if dia is None:
            dia = {"data": horario.data, "itens": [], "_por_evento": {}}
            indice_do_dia[horario.data] = dia
            dias.append(dia)
        item = dia["_por_evento"].get(horario.evento_id)
        if item is None:
            item = {"evento": horario.evento, "horarios": []}
            dia["_por_evento"][horario.evento_id] = item
            dia["itens"].append(item)
        item["horarios"].append(horario)

    for dia in dias:
        del dia["_por_evento"]
    return dias


class Submissao(models.Model):
    """Submissão de trabalhos: uma só para a semana inteira.

    Não é por evento nem por área — é um link único, o mesmo para todo mundo.
    Por isso existe uma linha só, criada pela migração e carregada por
    `Submissao.atual()`. Mora no banco, e não no HTML, pela mesma razão das
    inscrições: o endereço e o prazo mudam depois de o site já estar no ar.
    """

    aberta = models.BooleanField(
        "submissão aberta",
        default=False,
        help_text="Desmarcada, a página mostra “A submissão abre em breve”.",
    )
    link = models.URLField(
        "link da submissão",
        max_length=300,
        blank=True,
        help_text="Endereço do formulário de envio. Sem ele não aparece botão, "
        "mesmo com a submissão marcada como aberta.",
    )
    prazo = models.DateField(
        "prazo de envio",
        null=True,
        blank=True,
        help_text="Opcional. Sem data preenchida, a página não fala em prazo.",
    )

    class Meta:
        verbose_name = "submissão de trabalhos"
        verbose_name_plural = "submissão de trabalhos"

    def __str__(self):
        return "Submissão de trabalhos"

    def save(self, *args, **kwargs):
        # Uma linha só: qualquer save escreve sempre na mesma.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def atual(cls):
        """A configuração da submissão, mesmo que a linha ainda não exista.

        Devolver um objeto vazio em vez de None deixa o template simples: ele
        pergunta `submissao.mostra_botao` e pronto, sem checar nulo antes.
        """
        return cls.objects.first() or cls()

    @property
    def mostra_botao(self):
        """Só há botão quando a submissão está aberta e há para onde ir."""
        return bool(self.aberta and self.link)

    @property
    def situacao(self):
        """O que a página inicial mostra hoje na seção de trabalhos."""
        if self.mostra_botao:
            return "botão “Enviar meu trabalho”"
        if self.aberta:
            return "marcada como aberta, mas sem link — nenhum botão aparece"
        return "“A submissão abre em breve”"


class Cartao(models.Model):
    """Um dos cartões de evento da página inicial.

    O que aparece no cartão era HTML fixo no template. Virou dado porque o
    site roda em container num servidor que a organização não administra:
    trocar um título ou um responsável exigiria reconstruir a imagem. Aqui,
    é um formulário no painel.

    O estado da inscrição continua vindo da área (`Area.inscricoes_abertas` e
    `link_inscricao`) — é a coordenação que mexe nisso, e não muda aqui.
    """

    area = models.ForeignKey(
        Area,
        verbose_name="curso/área",
        on_delete=models.PROTECT,
        related_name="cartoes",
        help_text="De onde vêm o botão de inscrição e o link do cronograma.",
    )
    trilha = models.CharField(
        "etiqueta",
        max_length=60,
        blank=True,
        help_text="O selo verde no alto do cartão. Em branco, usa o nome do "
        "curso/área.",
    )
    titulo = models.CharField("título", max_length=160)
    responsavel = models.CharField(
        "responsável",
        max_length=120,
        blank=True,
        help_text="Em branco, o cartão mostra “a confirmar”.",
    )
    coordenacao = models.CharField(
        "coordenação",
        max_length=160,
        blank=True,
        help_text="Vem depois do responsável, ex.: “Coordenação de Biologia”.",
    )
    descricao = models.TextField(
        "descrição",
        help_text="Duas ou três frases sobre o evento.",
    )
    programacao_rotulo = models.CharField(
        "data da programação",
        max_length=40,
        blank=True,
        help_text="Como aparece no cartão, ex.: “27/10” ou “29 e 30/10”.",
    )
    programacao = models.TextField(
        "programação",
        blank=True,
        help_text="Um item por linha. Sem nenhum, o cartão não mostra a lista.",
    )
    link_horarios = models.URLField(
        "link dos horários",
        max_length=300,
        blank=True,
        help_text="Em branco, o botão “Ver horários” leva ao cronograma do "
        "site. Preenchido, leva a este endereço — para um curso que publique "
        "a programação em página própria.",
    )
    ordem = models.PositiveSmallIntegerField(
        "ordem",
        default=0,
        help_text="Menor primeiro. Em empate, vale o título.",
    )
    publicado = models.BooleanField(
        "publicado",
        default=True,
        help_text="Desmarque para tirar o cartão do site sem apagá-lo.",
    )

    class Meta:
        verbose_name = "cartão da página inicial"
        verbose_name_plural = "cartões da página inicial"
        ordering = ["ordem", "titulo"]

    def __str__(self):
        return self.titulo

    @property
    def etiqueta(self):
        """O selo do alto. Sem etiqueta própria, é o nome do curso/área."""
        return self.trilha or self.area.nome

    @property
    def horarios_fora(self):
        """Se o “Ver horários” sai do site. Decide o target do link."""
        return bool(self.link_horarios)

    @property
    def url_horarios(self):
        """Para onde vai o “Ver horários” deste cartão.

        Por padrão, o cronograma do próprio site, já filtrado pela área. Um
        curso que publique a programação em outro lugar põe o endereço em
        `link_horarios` e o botão passa a apontar para lá.
        """
        if self.link_horarios:
            return self.link_horarios
        return f"{reverse('cronograma')}?area={self.area.slug}"

    @property
    def itens_programacao(self):
        """A programação como lista, uma linha por item."""
        return [linha.strip() for linha in self.programacao.splitlines() if linha.strip()]


class AnexoQuerySet(models.QuerySet):
    def publicados(self):
        return self.filter(publicado=True)

    def com_conteudo(self):
        """Só o que já dá para baixar ou ler — sem os “em breve”.

        Serve para a página inicial decidir se vale mandar alguém para a
        página de submissão: uma lista inteira de "em breve" não vale.
        """
        return self.publicados().exclude(arquivo="", link="", texto="")


class Anexo(models.Model):
    """Um documento da página de submissão: regulamento, modelo, edital.

    Pode ser um arquivo enviado pelo painel ou um endereço de fora — alguns
    documentos já vivem no Drive da coordenação e não vale a pena duplicar.
    É um ou outro, nunca os dois, para não haver dúvida sobre qual dos dois
    o botão baixa.

    Os arquivos enviados vão para MEDIA_ROOT, que no servidor é um volume: o
    próximo `docker compose up --build` refaz a imagem, e o que estivesse
    dentro dela sumiria.
    """

    titulo = models.CharField("título", max_length=120)
    slug = models.SlugField(
        "endereço curto",
        max_length=120,
        unique=True,
        blank=True,
        help_text="Preenchido automaticamente a partir do título. É o "
        "endereço da versão do documento que fica no site.",
    )
    descricao = models.CharField(
        "descrição",
        max_length=200,
        blank=True,
        help_text="Uma linha explicando o que é. Opcional.",
    )
    arquivo = models.FileField(
        "arquivo",
        upload_to="submissao/",
        blank=True,
        help_text="PDF, DOCX, ODT… Deixe em branco se for usar um link, ou se "
        "o documento ainda não ficou pronto.",
    )
    link = models.URLField(
        "link",
        max_length=300,
        blank=True,
        help_text="Para um documento que já está publicado em outro lugar. "
        "Deixe em branco se enviou um arquivo.",
    )
    texto = models.TextField(
        "texto no site",
        blank=True,
        help_text="Opcional. Preenchido, o documento também ganha uma página "
        "no próprio site, para ler sem baixar nada — é o caso do regulamento. "
        "Uma linha começando com ## vira título; com - vira item de lista; "
        "linha em branco separa parágrafos.",
    )
    ordem = models.PositiveSmallIntegerField(
        "ordem",
        default=0,
        help_text="Menor primeiro. Empate, ordena pelo título.",
    )
    publicado = models.BooleanField(
        "publicado",
        default=True,
        help_text="Desmarque para tirar da página sem apagar o documento.",
    )

    objects = AnexoQuerySet.as_manager()

    class Meta:
        verbose_name = "documento da submissão"
        verbose_name_plural = "documentos da submissão"
        ordering = ["ordem", "titulo"]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titulo)[:120]
        super().save(*args, **kwargs)

    def clean(self):
        # Um ou outro, nunca os dois: os dois preenchidos deixariam o botão
        # ambíguo. Nenhum dos dois é permitido de propósito — é o documento
        # que a organização já anunciou e ainda não ficou pronto; a página o
        # mostra como "em breve", e não como um botão que não abre nada.
        if self.arquivo and self.link:
            raise ValidationError(
                "Escolha um dos dois: ou envia o arquivo, ou põe o link. "
                "Não dá para ter os dois no mesmo documento."
            )

    @property
    def disponivel(self):
        """Há o que baixar hoje? Sem arquivo e sem link, é um "em breve"."""
        return bool(self.arquivo or self.link)

    @property
    def tem_pagina(self):
        """O documento também pode ser lido no próprio site."""
        return bool(self.texto.strip())

    @property
    def url_pagina(self):
        return reverse("documento", args=[self.slug])

    @property
    def externo(self):
        """Mora fora do site? Então o botão abre em outra aba."""
        return bool(self.link) and not self.arquivo

    @property
    def url(self):
        """Para onde o botão de baixar vai. Vazio quando não há o que baixar."""
        if not self.disponivel:
            return ""
        return self.link if self.externo else self.arquivo.url

    @property
    def formato(self):
        """A etiqueta do cartão: PDF, DOCX, “link”, “site” ou “em breve”."""
        if not self.disponivel:
            # Sem arquivo, mas com texto, ainda há o que ler: a página.
            return "site" if self.tem_pagina else "em breve"
        if self.externo:
            return "link"
        sufixo = Path(self.arquivo.name).suffix.lstrip(".")
        return sufixo.upper() or "arquivo"

    @property
    def tamanho(self):
        """Tamanho legível, ou vazio quando o arquivo não está mais no disco.

        Não está mais no disco acontece: alguém restaura um banco sem restaurar
        o volume. Melhor a página não mostrar tamanho do que estourar erro 500.
        """
        if self.externo or not self.arquivo:
            return ""
        try:
            bytes_ = self.arquivo.size
        except (OSError, ValueError):
            return ""
        if bytes_ < 1024 * 1024:
            return f"{max(bytes_ // 1024, 1)} KB"
        return f"{bytes_ / (1024 * 1024):.1f} MB".replace(".", ",")


def areas_do_usuario(user):
    """Áreas que este usuário pode administrar.

    É a única fonte de verdade das permissões — as views e os formulários
    todos passam por aqui, para que a regra não fique espalhada.
    """
    if not user.is_authenticated:
        return Area.objects.none()
    if user.is_superuser:
        return Area.objects.filter(ativo=True)
    return user.areas_geridas.filter(ativo=True)
