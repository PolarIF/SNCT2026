"""Cria a conta de administrador a partir de variáveis de ambiente.

Existe porque quem opera o servidor não é quem administra o site: a TI do
campus sobe o container e a organização da SNCT precisa entrar no /admin/ sem
depender de alguém rodar `createsuperuser` no terminal de lá.

Roda a cada início do container e não faz nada se a conta já existir, então
trocar a senha pelo /admin/ não é desfeito no próximo restart.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria o administrador inicial com ADMIN_USUARIO e ADMIN_SENHA, se ainda não existir."

    def handle(self, *args, **options):
        usuario = os.environ.get("ADMIN_USUARIO", "").strip()
        senha = os.environ.get("ADMIN_SENHA", "")

        if not usuario or not senha:
            self.stdout.write("ADMIN_USUARIO/ADMIN_SENHA não definidos: nenhuma conta criada.")
            return

        User = get_user_model()
        if User.objects.filter(username=usuario).exists():
            self.stdout.write(f"A conta '{usuario}' já existe: nada a fazer.")
            return

        User.objects.create_superuser(
            username=usuario,
            password=senha,
            email=os.environ.get("ADMIN_EMAIL", "") or "",
        )
        self.stdout.write(self.style.SUCCESS(f"Administrador '{usuario}' criado."))
        self.stdout.write("Troque a senha no /admin/ assim que entrar pela primeira vez.")
