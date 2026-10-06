"""Tira de Evento os campos de data e hora, já copiados para Horario.

Roda depois da 0010, que é quem copiou. Nada se perde: o que estava nessas
três colunas está, neste ponto, dentro de `eventos_horario`.

A ordem das operações aqui foi escolhida para que a volta também funcione, e
não é óbvia. Na reversão o Django desfaz de trás para a frente:

    RemoveField (×3)  ->  recria as colunas, vazias
    RunPython         ->  preenche a partir de Horario      <- precisa estar aqui
    AlterField (×2)   ->  devolve o NOT NULL às colunas

Sem o RunPython no meio, o AlterField tentaria pôr NOT NULL em coluna vazia e
a reversão quebraria em qualquer banco com um evento sequer. Foi o que
aconteceu na primeira versão desta migração.

O afrouxamento para NULL não muda nada na ida — as colunas saem logo em
seguida. Ele existe só para que a recriação, na volta, possa nascer vazia.
"""

from django.db import migrations, models


def nada_a_fazer(apps, schema_editor):
    """Na ida não há o que fazer: a 0010 já copiou tudo para Horario."""


def devolver_para_evento(apps, schema_editor):
    """Escreve de volta em Evento o horário mais cedo de cada um.

    Um evento com mais de um horário perde os demais na volta — do outro lado
    não existe onde guardá-los, que é justamente o motivo desta mudança. Por
    isso reverter em produção é recurso de emergência, e não rotina: o certo
    é restaurar o backup, que está documentado no IMPLANTACAO.md.
    """
    Evento = apps.get_model("eventos", "Evento")
    Horario = apps.get_model("eventos", "Horario")

    for evento in Evento.objects.all().iterator():
        primeiro = (
            Horario.objects.filter(evento=evento)
            .order_by("data", "hora_inicio")
            .first()
        )
        if primeiro is None:
            # Evento sem horário nenhum não tem o que devolver. Como as colunas
            # vão voltar a ser NOT NULL logo adiante, ele impediria a reversão
            # inteira — e sumir com ele seria pior. Fica o aviso alto.
            raise RuntimeError(
                f"O evento {evento.pk} ({evento.titulo!r}) não tem nenhum "
                "horário, e as colunas de data e hora não aceitam vazio. "
                "Cadastre um horário para ele, ou apague o evento, antes de "
                "reverter esta migração."
            )
        evento.data = primeiro.data
        evento.hora_inicio = primeiro.hora_inicio
        evento.hora_fim = primeiro.hora_fim
        evento.save(update_fields=["data", "hora_inicio", "hora_fim"])


class Migration(migrations.Migration):

    dependencies = [
        ("eventos", "0010_horarios_do_evento"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="evento",
            options={
                "ordering": ["titulo"],
                "verbose_name": "evento",
                "verbose_name_plural": "eventos",
            },
        ),
        migrations.RemoveIndex(
            model_name="evento",
            name="eventos_eve_data_45ab24_idx",
        ),
        migrations.AlterField(
            model_name="evento",
            name="data",
            field=models.DateField(blank=True, null=True, verbose_name="data"),
        ),
        migrations.AlterField(
            model_name="evento",
            name="hora_inicio",
            field=models.TimeField(
                blank=True, null=True, verbose_name="horário de início"
            ),
        ),
        migrations.RunPython(nada_a_fazer, devolver_para_evento),
        migrations.RemoveField(
            model_name="evento",
            name="data",
        ),
        migrations.RemoveField(
            model_name="evento",
            name="hora_inicio",
        ),
        migrations.RemoveField(
            model_name="evento",
            name="hora_fim",
        ),
    ]
