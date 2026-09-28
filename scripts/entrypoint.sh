#!/bin/sh
# Roda a cada início do container, antes do gunicorn.
#
# Quem opera o servidor não é quem administra o site, então tudo que
# normalmente se faria à mão depois do deploy acontece aqui: migrar o banco e
# garantir que existe uma conta de administrador. As duas etapas são
# idempotentes — reiniciar o container não desfaz nada.
set -e

# Com mais de um worker, cada um escreve seus contadores num arquivo deste
# diretório e o /metrics soma todos (ver gunicorn.conf.py). O que sobrou da
# execução anterior precisa sair, senão as contagens vêm somadas com as de
# processos que já morreram.
if [ -n "${PROMETHEUS_MULTIPROC_DIR:-}" ]; then
    echo "→ limpando métricas da execução anterior"
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
    rm -f "$PROMETHEUS_MULTIPROC_DIR"/*.db 2>/dev/null || true
fi

echo "→ aplicando migrações"
python manage.py migrate --noinput

echo "→ conferindo a conta de administrador"
python manage.py criar_admin

echo "→ subindo a aplicação"
exec "$@"
