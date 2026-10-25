from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
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
    tem_inscricao = models.BooleanField(
        "esta atividade tem inscrição",
        default=True,
        help_text="Desmarque para atividade aberta, em que é só chegar: o "
        "cronograma não mostra botão de inscrição e avisa que a entrada é livre.",
    )
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

        Atividade marcada como sem inscrição nunca tem botão: sem isso, uma
        palestra aberta herdava o "Inscreva-se" do curso e mandava a pessoa
        para um formulário de que ela não precisava.

        Link próprio aparece sempre: quem o colou aqui quis inscrição nesta
        atividade, e não faria sentido depender do interruptor da área. Sem
        link próprio, o botão é o da área e obedece ao interruptor dela.
        """
        if not self.tem_inscricao:
            return False
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
    """A submissão de trabalhos de uma mostra.

    Era uma só para a semana inteira. Virou uma por mostra quando a semana
    passou a ter duas — a Científica e a Empreendedora e Tecnológica —, cada
    uma com regulamento, prazo, datas e formulário próprios. As duas nascem
    da migração; não é algo que se cria toda semana, e por isso o painel só
    edita.

    Mora no banco, e não no HTML, pela mesma razão das inscrições: o
    endereço e o prazo mudam depois de o site já estar no ar.
    """

    nome = models.CharField("mostra", max_length=80, unique=True)
    slug = models.SlugField(
        "endereço curto",
        max_length=80,
        unique=True,
        blank=True,
        help_text="Preenchido automaticamente a partir do nome. É a âncora "
        "da mostra em /trabalhos/.",
    )
    resumo = models.TextField(
        "texto de apresentação",
        blank=True,
        help_text="Aparece na página inicial e no alto da mostra em "
        "/trabalhos/. **texto** vira negrito; linha em branco separa "
        "parágrafos.",
    )
    aberta = models.BooleanField(
        "submissão aberta",
        default=False,
        help_text="Desmarcada, a página mostra “A submissão abre em breve”.",
    )
    prazo = models.DateField(
        "prazo de envio",
        null=True,
        blank=True,
        help_text="Opcional. É o último dia de envio: no dia seguinte a página "
        "mostra “Prazo encerrado” sozinha. Sem data, a página não fala em prazo.",
    )
    ordem = models.PositiveSmallIntegerField(
        "ordem",
        default=0,
        help_text="Menor primeiro, na página inicial e em /trabalhos/.",
    )

    class Meta:
        verbose_name = "submissão de trabalhos"
        verbose_name_plural = "submissões de trabalhos"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nome)[:80]
        super().save(*args, **kwargs)

    @cached_property
    def links_de_envio(self):
        """Os botões de envio, em ordem. Lista, e não queryset: o template
        pergunta por eles mais de uma vez, e cada pergunta seria uma consulta."""
        return list(self.links.all())

    @property
    def encerrada(self):
        """O prazo já passou? Então a submissão acabou, marcada ou não.

        O prazo vale o dia inteiro: no dia 12 ainda dá para enviar, e no 13 a
        página já diz "Prazo encerrado". Fecha sozinho, sem ninguém precisar
        lembrar de desmarcar a caixa — e desmarcar depois do prazo também
        não faz a página voltar a dizer "Em breve", que seria mentira.

        O dia é o do fuso do campus (TIME_ZONE), e não o do servidor.
        """
        return bool(self.prazo and timezone.localdate() > self.prazo)

    @property
    def mostra_botao(self):
        """Só há botão quando a submissão está aberta, dentro do prazo e há
        para onde ir."""
        return bool(self.aberta and not self.encerrada and self.links_de_envio)

    @property
    def tem_documento(self):
        """Já há documento para ler ou baixar? Apenas anunciado não conta."""
        return self.anexos.com_conteudo().exists()

    @property
    def situacao(self):
        """O que a página inicial mostra hoje no cartão desta mostra."""
        if self.encerrada:
            return "“Prazo encerrado” — o prazo já passou, e o botão sumiu sozinho"
        if self.mostra_botao:
            return "botão “Enviar meu trabalho”"
        if self.aberta:
            return "marcada como aberta, mas sem link — nenhum botão aparece"
        return "“A submissão abre em breve”"


class LinkDeEnvio(models.Model):
    """Um formulário de envio de uma mostra.

    É uma lista porque nem toda mostra tem um formulário só: a Empreendedora
    e Tecnológica tem um para estudantes e outro para professores. Cada link
    vira um botão, com o texto que a organização escrever.
    """

    submissao = models.ForeignKey(
        Submissao,
        verbose_name="mostra",
        on_delete=models.CASCADE,
        related_name="links",
    )
    rotulo = models.CharField(
        "texto do botão",
        max_length=60,
        help_text="Ex.: “Enviar meu trabalho”, ou “Sou estudante” quando há "
        "um formulário para cada público.",
    )
    url = models.URLField("link do formulário", max_length=300)
    ordem = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "link de envio"
        verbose_name_plural = "links de envio"
        ordering = ["ordem", "pk"]

    def __str__(self):
        return self.rotulo


class Etapa(models.Model):
    """Uma data do cronograma de uma mostra: submissão, avaliação, resultado.

    Eram quatro datas fixas no HTML de /trabalhos/. Viraram dado quando a
    segunda mostra chegou com calendário próprio.
    """

    submissao = models.ForeignKey(
        Submissao,
        verbose_name="mostra",
        on_delete=models.CASCADE,
        related_name="etapas",
    )
    titulo = models.CharField("etapa", max_length=60)
    inicio = models.DateField("dia")
    fim = models.DateField(
        "até",
        null=True,
        blank=True,
        help_text="Só quando a etapa dura mais de um dia.",
    )
    descricao = models.CharField("descrição", max_length=160, blank=True)

    class Meta:
        verbose_name = "etapa do cronograma"
        verbose_name_plural = "etapas do cronograma"
        # Pela data, e não por um campo de ordem: é um cronograma. Etapas que
        # começam juntas (o envio e a avaliação correm em paralelo) ficam na
        # ordem em que terminam.
        ordering = ["inicio", "fim", "pk"]

    def __str__(self):
        return self.titulo

    def clean(self):
        if self.fim and self.inicio and self.fim < self.inicio:
            raise ValidationError({"fim": "O fim tem que ser depois do início."})


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

    submissao = models.ForeignKey(
        Submissao,
        verbose_name="mostra",
        on_delete=models.PROTECT,
        related_name="anexos",
    )
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
        ordering = ["submissao__ordem", "ordem", "titulo"]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._slug_livre()
        super().save(*args, **kwargs)

    def _slug_livre(self):
        """O slug do título, ou com o nome da mostra quando ele já existe.

        Cada mostra tem o seu “Regulamento”, e o endereço é um só para o site
        inteiro (/trabalhos/<slug>/). O primeiro fica com /regulamento/ — que
        é o endereço já divulgado —, e o seguinte vira
        /regulamento-mostra-empreendedora-e-tecnologica/.
        """
        base = slugify(self.titulo)[:120]
        outros = Anexo.objects.exclude(pk=self.pk)
        if not outros.filter(slug=base).exists():
            return base
        candidato = f"{base}-{self.submissao.slug}"[:120]
        n = 2
        while outros.filter(slug=candidato).exists():
            candidato = f"{base}-{self.submissao.slug}"[: 120 - len(str(n)) - 1] + f"-{n}"
            n += 1
        return candidato

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


# ------------------------------------------------------------ textos do site

DIAS_DA_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


class Site(models.Model):
    """Os textos do site que não são de nenhum curso nem de nenhuma mostra.

    Eram HTML fixo nos templates: as datas da semana (que apareciam em meia
    dúzia de lugares), o tema, o texto de cada seção da página inicial, o
    rodapé. Viraram dado pela mesma razão de todo o resto: o site roda em
    container, e trocar uma frase não pode exigir reimplantar.

    É uma linha só, criada pela migração, e carregada por `Site.atual()` em
    toda página (ver eventos/context_processors.py). As datas ficam em campo
    de data, e não em texto, porque é delas que saem "27 a 30 de outubro de
    2026", "de terça a sexta" e a contagem regressiva — escrever as três à
    mão era o jeito de uma delas ficar errada.

    O que continua fixo no código: o layout, as cores, o menu e as imagens.
    """

    # a semana
    edicao = models.CharField(
        "edição", max_length=10, help_text="Como aparece antes de “SNCT”, ex.: “23ª”."
    )
    nome = models.CharField("nome do evento", max_length=120)
    tema = models.CharField("tema", max_length=80, blank=True)
    data_inicio = models.DateField("primeiro dia")
    data_fim = models.DateField("último dia")
    local = models.CharField(
        "onde", max_length=160, help_text="Aparece na ficha da seção “Sobre”."
    )

    # página inicial
    heroi_texto = models.TextField(
        "texto de abertura",
        help_text="O parágrafo do topo da página inicial, abaixo da logo.",
    )
    programacao_titulo = models.CharField("título da programação geral", max_length=120)
    eventos_titulo = models.CharField("título da seção de eventos", max_length=120)
    eventos_texto = models.TextField("texto da seção de eventos", blank=True)
    guia_titulo = models.CharField("título do guia de inscrição", max_length=80)
    guia_subtitulo = models.CharField(
        "subtítulo do guia de inscrição", max_length=120, blank=True
    )
    guia_nota = models.TextField(
        "nota no fim do guia",
        blank=True,
        help_text="Uma linha abaixo dos passos. Em branco, não aparece.",
    )
    sobre_titulo = models.CharField("título da seção “Sobre”", max_length=120)
    sobre_texto = models.TextField("texto da seção “Sobre”")

    # outras páginas
    cronograma_texto = models.TextField(
        "texto de abertura do cronograma", blank=True
    )
    trabalhos_texto = models.TextField(
        "texto de abertura da submissão",
        blank=True,
        help_text="O parágrafo do topo de /trabalhos/.",
    )

    # rodapé e compartilhamento
    descricao = models.CharField(
        "descrição para buscadores e WhatsApp",
        max_length=300,
        help_text="O resumo que aparece embaixo do link no Google e quando o "
        "site é compartilhado.",
    )
    rodape_credito = models.CharField("crédito no rodapé", max_length=120, blank=True)
    portal_url = models.URLField(
        "link do portal do Campus", max_length=300, blank=True
    )

    class Meta:
        verbose_name = "textos do site"
        verbose_name_plural = "textos do site"

    def __str__(self):
        return "Textos do site"

    def save(self, *args, **kwargs):
        # Uma linha só: qualquer save escreve sempre na mesma.
        self.pk = 1
        super().save(*args, **kwargs)

    def clean(self):
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError(
                {"data_fim": "O último dia tem que ser depois do primeiro."}
            )

    @classmethod
    def atual(cls):
        """Os textos do site. A linha vem da migração; se alguém a apagar,
        devolve uma em branco em vez de derrubar todas as páginas."""
        return cls.objects.filter(pk=1).first() or cls()

    # As três listas, com nome de gente: o Django chamaria de *_set.
    @property
    def dias_da_programacao(self):
        return self.diadaprogramacao_set.all()

    @property
    def passos_da_inscricao(self):
        return self.passodainscricao_set.all()

    @property
    def itens_da_ficha(self):
        return self.itemdaficha_set.all()

    @property
    def sigla(self):
        """“23ª SNCT”."""
        return f"{self.edicao} SNCT".strip()

    @property
    def titulo_completo(self):
        """“23ª Semana Nacional de Ciência e Tecnologia”."""
        return f"{self.edicao} {self.nome}".strip()

    @property
    def periodo(self):
        """“27 a 30 de outubro de 2026”, ou “30 de setembro a 2 de outubro de
        2026” quando a semana atravessa o mês."""
        ini, fim = self.data_inicio, self.data_fim
        if not ini or not fim:
            return ""
        if ini == fim:
            return f"{ini.day} de {MESES[ini.month - 1]} de {ini.year}"
        if (ini.month, ini.year) == (fim.month, fim.year):
            return f"{ini.day} a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"
        if ini.year == fim.year:
            return (
                f"{ini.day} de {MESES[ini.month - 1]} a "
                f"{fim.day} de {MESES[fim.month - 1]} de {fim.year}"
            )
        return (
            f"{ini.day} de {MESES[ini.month - 1]} de {ini.year} a "
            f"{fim.day} de {MESES[fim.month - 1]} de {fim.year}"
        )

    @property
    def dias_da_semana(self):
        """“de terça a sexta”."""
        ini, fim = self.data_inicio, self.data_fim
        if not ini or not fim or ini == fim:
            return ""
        return f"de {DIAS_DA_SEMANA[ini.weekday()]} a {DIAS_DA_SEMANA[fim.weekday()]}"


class ItemDoSite(models.Model):
    """Base das três listas que pertencem aos textos do site."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    ordem = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        abstract = True
        ordering = ["ordem", "pk"]


class DiaDaProgramacao(ItemDoSite):
    """Um cartão da “Programação geral”: o dia e o que acontece nele."""

    rotulo = models.CharField(
        "dia", max_length=40, help_text="Como aparece no cartão, ex.: “29 e 30/10”."
    )
    dia_da_semana = models.CharField(
        "dia da semana", max_length=40, blank=True, help_text="Ex.: “quinta e sexta”."
    )
    texto = models.CharField("o que acontece", max_length=300)

    class Meta(ItemDoSite.Meta):
        verbose_name = "dia da programação geral"
        verbose_name_plural = "dias da programação geral"

    def __str__(self):
        return self.rotulo


class PassoDaInscricao(ItemDoSite):
    """Um passo do guia “Como se inscrever”."""

    titulo = models.CharField("passo", max_length=80)
    texto = models.TextField("explicação")

    class Meta(ItemDoSite.Meta):
        verbose_name = "passo do guia de inscrição"
        verbose_name_plural = "passos do guia de inscrição"

    def __str__(self):
        return self.titulo


class ItemDaFicha(ItemDoSite):
    """Uma linha da ficha da seção “Sobre” (Para quem, Contato…).

    “Quando” e “Onde” não são itens: saem das datas e do local da semana, e
    aparecem sempre primeiro.
    """

    rotulo = models.CharField("rótulo", max_length=40)
    texto = models.CharField("texto", max_length=300)

    class Meta(ItemDoSite.Meta):
        verbose_name = "item da ficha"
        verbose_name_plural = "itens da ficha"

    def __str__(self):
        return self.rotulo
