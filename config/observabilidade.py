"""Observabilidade do SNCT: as métricas do contrato comum aos três projetos.

Por que um middleware próprio em vez de confiar no django-prometheus: ele emite
`django_http_requests_total_by_method_total` e afins — nomes próprios, status
agrupado por classe. O contrato dos três pede `http_requests_total` com os
mesmos rótulos e os mesmos buckets, para uma consulta/painel/alerta servir aos
três. As métricas de BANCO do django-prometheus ficam (não colidem).
"""
from __future__ import annotations

import time

from prometheus_client import Counter, Histogram

# Os mesmos onze buckets dos outros dois projetos. Buckets diferentes tornam
# impossível comparar latência entre eles.
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

# `projeto` NÃO entra aqui: é posto pelo Prometheus, no scrape (projeto=snct).
REQUISICOES = Counter(
    "http_requests_total",
    "Requisicoes HTTP atendidas",
    ["method", "route", "status"],
)
DURACAO = Histogram(
    "http_request_duration_seconds",
    "Duracao das requisicoes HTTP",
    ["method", "route"],
    buckets=BUCKETS,
)

ROTA_DESCONHECIDA = "<desconhecida>"

# Caminhos de infraestrutura: existem para o sistema se observar, não para
# servir gente. Medi-los faz a raspagem (/metrics, 15s) e o healthcheck
# (/saude/, 30s) dominarem a série e inflarem o denominador de erro.
CAMINHOS_NAO_MEDIDOS = frozenset({"/metrics", "/saude/"})


class ObservabilidadeMiddleware:
    """Emite as duas métricas do contrato por requisição HTTP.

    Nas Tasks 2 e 3 esta mesma classe passa a capturar o Cf-Ray e a emitir a
    linha de acesso, a partir dos mesmos valores capturados aqui — sem recapturar.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inicio = time.perf_counter()
        response = self.get_response(request)
        duracao = time.perf_counter() - inicio

        caminho = request.path
        if caminho not in CAMINHOS_NAO_MEDIDOS:
            match = getattr(request, "resolver_match", None)
            rota = getattr(match, "route", None)
            # resolver_match.route não leva a barra inicial; normaliza para
            # casar o estilo dos outros projetos.
            if rota is not None:
                rota = "/" + rota if not rota.startswith("/") else rota
            else:
                rota = ROTA_DESCONHECIDA
            metodo = request.method or "GET"
            codigo = str(response.status_code)
            REQUISICOES.labels(method=metodo, route=rota, status=codigo).inc()
            DURACAO.labels(method=metodo, route=rota).observe(duracao)

        return response
