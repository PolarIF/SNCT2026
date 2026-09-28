# Imagem do site da SNCT — IFRO Campus Ariquemes.
#
# Tudo que a aplicação precisa está aqui dentro, inclusive os estáticos já
# processados. Fora do container só ficam: o arquivo .env e o volume do banco.

FROM python:3.13-slim

# Sem .pyc no disco, log saindo na hora (senão o `docker logs` fica mudo),
# e pip sem cache para a imagem não carregar lixo.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus

WORKDIR /app

# curl é usado pelo HEALTHCHECK. O psycopg vem em wheel binário, então não
# precisa de compilador nem de libpq do sistema.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# As dependências entram antes do código: assim o cache do Docker só é
# invalidado quando o requirements.txt muda, e não a cada ajuste de template.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Os estáticos são processados no build (nome com hash e versão comprimida),
# para o container subir sem depender de rede nem de escrita em disco.
# A SECRET_KEY aqui é descartável e só existe para o collectstatic rodar.
RUN SECRET_KEY=build-descartavel DEBUG=0 \
    python manage.py collectstatic --noinput --clear

# Roda como usuário comum. O diretório de dados é dele, porque é onde o
# SQLite escreve quando a instalação não usa PostgreSQL.
# /tmp/prometheus e onde os workers deixam seus contadores quando as metricas
# estao ligadas (ver gunicorn.conf.py). Precisa existir e ser do usuario snct;
# o entrypoint esvazia a cada start, senao sobra contador de worker morto.
RUN useradd --create-home --shell /bin/bash snct \
 && mkdir -p /dados /tmp/prometheus \
 && chown -R snct:snct /app /dados /tmp/prometheus
USER snct

VOLUME ["/dados"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS -H "Host: localhost" http://127.0.0.1:8000/saude/ || exit 1

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi", \
     "--config", "/app/gunicorn.conf.py", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "180", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
