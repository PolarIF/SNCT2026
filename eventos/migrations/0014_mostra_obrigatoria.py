"""Fecha o que a 0012 deixou aberto, agora que a 0013 preencheu tudo.

O link único sai de Submissao (mora em LinkDeEnvio), o endereço curto da
mostra passa a ser único e todo documento passa a ter mostra.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eventos", "0013_as_duas_mostras"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="submissao",
            name="link",
        ),
        migrations.AlterField(
            model_name="submissao",
            name="nome",
            field=models.CharField(max_length=80, unique=True, verbose_name="mostra"),
        ),
        migrations.AlterField(
            model_name="submissao",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text="Preenchido automaticamente a partir do nome. É a âncora da mostra em /trabalhos/.",
                max_length=80,
                unique=True,
                verbose_name="endereço curto",
            ),
        ),
        migrations.AlterField(
            model_name="anexo",
            name="submissao",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="anexos",
                to="eventos.submissao",
                verbose_name="mostra",
            ),
        ),
        migrations.AlterModelOptions(
            name="anexo",
            options={
                "ordering": ["submissao__ordem", "ordem", "titulo"],
                "verbose_name": "documento da submissão",
                "verbose_name_plural": "documentos da submissão",
            },
        ),
    ]
