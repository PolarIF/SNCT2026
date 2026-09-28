"""Configuração do gunicorn.

Existe por um motivo só: as métricas do Prometheus quebram quando há mais de
um worker, e o conserto tem de ficar do lado do gunicorn.

Cada worker é um processo com sua própria memória, então cada um mantém seus
próprios contadores. O /metrics é respondido por um worker sorteado a cada
coleta, e o Prometheus vê a série pulando entre três valores diferentes.
Toda queda é lida como reinício de contador, e o `increase()` soma tudo de
novo: medimos 144 "reinícios" por hora e um total de 30 mil requisições onde
tinham acontecido 40.

A correção é o modo multiprocesso do prometheus_client: os workers escrevem
em arquivos de um diretório comum (PROMETHEUS_MULTIPROC_DIR) e o /metrics
soma todos na hora de responder. Falta só avisar quando um worker morre —
é o que o child_exit abaixo faz. Sem isso, os arquivos de workers mortos
ficam no diretório e o total só cresce.
"""

import os


def child_exit(server, worker):
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(worker.pid)
