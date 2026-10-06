"""Cria a tabela de dias e horários e copia para ela o que já existe.

Esta migração não apaga nada: ela só acrescenta a tabela nova e preenche uma
linha por evento, a partir dos campos `data`, `hora_inicio` e `hora_fim` que
ainda estão em Evento. A remoção desses campos é a migração seguinte, e só
acontece depois que esta terminou de copiar.

Em PostgreSQL — o banco da VPS — o DDL é transacional: ou a sequência inteira
passa, ou o banco fica exatamente como estava. Mesmo assim, backup antes de
implantar; o comando está no IMPLANTACAO.md.
"""

import django.db.models.deletion
from django.db import migrations, models


def copiar_para_horarios(apps, schema_editor):
    """Uma linha em Horario para cada evento que já existe."""
    Evento = apps.get_model("eventos", "Evento")
    Horario = apps.get_model("eventos", "Horario")

    Horario.objects.bulk_create(
        [
            Horario(
                evento=evento,
                data=evento.data,
                hora_inicio=evento.hora_inicio,
                hora_fim=evento.hora_fim,
            )
            for evento in Evento.objects.all().iterator()
        ]
    )


def nada_a_desfazer(apps, schema_editor):
    """Reverter esta migração não precisa apagar linha nenhuma.

    A devolução dos dados para Evento acontece na 0011, que é revertida antes
    desta — tem de ser lá, porque é lá que as colunas de volta ainda estão
    vazias e precisam ser preenchidas. Aqui, logo em seguida, o próprio
    CreateModel ao contrário derruba a tabela inteira.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("eventos", "0009_documentos_previstos"),
    ]

    operations = [
        migrations.CreateModel(
            name="Horario",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("data", models.DateField(verbose_name="dia")),
                ("hora_inicio", models.TimeField(verbose_name="horário de início")),
                (
                    "hora_fim",
                    models.TimeField(
                        blank=True, null=True, verbose_name="horário de término"
                    ),
                ),
                (
                    "evento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="horarios",
                        to="eventos.evento",
                        verbose_name="evento",
                    ),
                ),
            ],
            options={
                "verbose_name": "dia e horário",
                "verbose_name_plural": "dias e horários",
                "ordering": ["data", "hora_inicio"],
            },
        ),
        migrations.AddIndex(
            model_name="horario",
            index=models.Index(
                fields=["data", "hora_inicio"], name="eventos_hor_data_d5338e_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="horario",
            constraint=models.UniqueConstraint(
                fields=("evento", "data", "hora_inicio"), name="horario_sem_repeticao"
            ),
        ),
        migrations.RunPython(copiar_para_horarios, nada_a_desfazer),
    ]
