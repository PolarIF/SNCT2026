#!/bin/sh
# Roda a cada início do container, antes do gunicorn.
#
# Quem opera o servidor não é quem administra o site, então tudo que
# normalmente se faria à mão depois do deploy acontece aqui: migrar o banco e
# garantir que existe uma conta de administrador. As duas etapas são
# idempotentes — reiniciar o container não desfaz nada.
set -e

echo "→ aplicando migrações"
python manage.py migrate --noinput

echo "→ conferindo a conta de administrador"
python manage.py criar_admin

echo "→ subindo a aplicação"
exec "$@"
