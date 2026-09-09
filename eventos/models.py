from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
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
    data = models.DateField("data")
    hora_inicio = models.TimeField("horário de início")
    hora_fim = models.TimeField("horário de término", null=True, blank=True)
    local = models.CharField("local", max_length=120, blank=True)
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
        ordering = ["data", "hora_inicio", "titulo"]
        indexes = [models.Index(fields=["data", "hora_inicio"])]

    def __str__(self):
        return f"{self.data:%d/%m} {self.hora_inicio:%H:%M} — {self.titulo}"

    def clean(self):
        if self.hora_fim and self.hora_inicio and self.hora_fim <= self.hora_inicio:
            raise ValidationError(
                {"hora_fim": "O horário de término tem que ser depois do de início."}
            )

    @property
    def horario(self):
        """"14:00 às 16:00" ou apenas "14:00" quando não há término."""
        inicio = self.hora_inicio.strftime("%H:%M")
        if not self.hora_fim:
            return inicio
        return f"{inicio} às {self.hora_fim:%H:%M}"


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
