"""Prepara a submissão para ter uma linha por mostra.

Só acrescenta: os campos novos de Submissao, as tabelas de links e de etapas
e a ligação do documento com a mostra, ainda opcional. Quem preenche é a
0013; quem aperta (tira o link antigo, exige mostra no documento) é a 0014.

São três migrações, e não uma, por causa do PostgreSQL: alterar uma tabela
depois de gravar dados nela, na mesma transação, esbarra em "pending trigger
events" das chaves estrangeiras.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eventos", "0011_evento_sem_data_propria"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="submissao",
            options={
                "ordering": ["ordem", "nome"],
                "verbose_name": "submissão de trabalhos",
                "verbose_name_plural": "submissões de trabalhos",
            },
        ),
        migrations.AddField(
            model_name="submissao",
            name="nome",
            field=models.CharField(default="", max_length=80, verbose_name="mostra"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="submissao",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text="Preenchido automaticamente a partir do nome. É a âncora da mostra em /trabalhos/.",
                max_length=80,
                verbose_name="endereço curto",
            ),
        ),
        migrations.AddField(
            model_name="submissao",
            name="resumo",
            field=models.TextField(
                blank=True,
                help_text="Aparece na página inicial e no alto da mostra em /trabalhos/. **texto** vira negrito; linha em branco separa parágrafos.",
                verbose_name="texto de apresentação",
            ),
        ),
        migrations.AddField(
            model_name="submissao",
            name="ordem",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="Menor primeiro, na página inicial e em /trabalhos/.",
                verbose_name="ordem",
            ),
        ),
        migrations.CreateModel(
            name="LinkDeEnvio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "rotulo",
                    models.CharField(
                        help_text="Ex.: “Enviar meu trabalho”, ou “Sou estudante” quando há um formulário para cada público.",
                        max_length=60,
                        verbose_name="texto do botão",
                    ),
                ),
                ("url", models.URLField(max_length=300, verbose_name="link do formulário")),
                ("ordem", models.PositiveSmallIntegerField(default=0, verbose_name="ordem")),
                (
                    "submissao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="eventos.submissao",
                        verbose_name="mostra",
                    ),
                ),
            ],
            options={
                "verbose_name": "link de envio",
                "verbose_name_plural": "links de envio",
                "ordering": ["ordem", "pk"],
            },
        ),
        migrations.CreateModel(
            name="Etapa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=60, verbose_name="etapa")),
                ("inicio", models.DateField(verbose_name="dia")),
                (
                    "fim",
                    models.DateField(
                        blank=True,
                        help_text="Só quando a etapa dura mais de um dia.",
                        null=True,
                        verbose_name="até",
                    ),
                ),
                ("descricao", models.CharField(blank=True, max_length=160, verbose_name="descrição")),
                (
                    "submissao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="etapas",
                        to="eventos.submissao",
                        verbose_name="mostra",
                    ),
                ),
            ],
            options={
                "verbose_name": "etapa do cronograma",
                "verbose_name_plural": "etapas do cronograma",
                "ordering": ["inicio", "fim", "pk"],
            },
        ),
        migrations.AddField(
            model_name="anexo",
            name="submissao",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="anexos",
                to="eventos.submissao",
                verbose_name="mostra",
            ),
        ),
    ]
