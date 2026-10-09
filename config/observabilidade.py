"""Observabilidade do SNCT: as métricas do contrato comum aos três projetos.

Por que um middleware próprio em vez de confiar no django-prometheus: ele emite
`django_http_requests_total_by_method_total` e afins — nomes próprios, status
agrupado por classe. O contrato dos três pede `http_requests_total` com os
mesmos rótulos e os mesmos buckets, para uma consulta/painel/alerta servir aos
três. As métricas de BANCO do django-prometheus ficam (não colidem).
"""
from __future__ import annotations

import ipaddress
import re
import time
import uuid
from contextvars import ContextVar

from django.conf import settings
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

# O verbo HTTP é controlado por quem chama: um cliente com método inventado
# (o gunicorn/WSGI deixa passar verbos arbitrários, ao contrário do uvicorn)
# viraria uma série nova a cada verbo diferente — cardinalidade sem limite,
# achado da varredura de segurança. Só os verbos reais entram crus no rótulo;
# o resto cai num balde fixo, igual ao <desconhecida> da rota.
METODOS_CONHECIDOS = frozenset(
    {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"}
)
METODO_DESCONHECIDO = "<desconhecido>"

# Caminhos de infraestrutura: existem para o sistema se observar, não para
# servir gente. Medi-los faz a raspagem (/metrics, 15s) e o healthcheck
# (/saude/, 30s) dominarem a série e inflarem o denominador de erro.
CAMINHOS_NAO_MEDIDOS = frozenset({"/metrics", "/saude/"})

# O Cf-Ray da Cloudflare: 16 hex + '-' + código de três maiúsculas do data
# center (ex.: 8a1b2c3d4e5f6789-GRU). Validar o formato impede que um cliente
# direto injete qualquer coisa (log forging) no id que vai para a auditoria.
_CF_RAY = re.compile(r"^[0-9a-f]{16}-[A-Z]{3}\Z")

# Contexto da requisição corrente, por task/thread. A linha de acesso (Task 3)
# lê daqui o cf_ray e o client_ip sem precisar do objeto request.
_CTX: ContextVar[dict] = ContextVar("obs_ctx", default={})


def contexto_atual() -> dict:
    """Contexto da requisição corrente (cf_ray, client_ip) para o log."""
    return _CTX.get()


def _peer_confiavel(remote_addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return False
    for cidr in settings.CIDRS_PROXY_CONFIAVEL:
        if ip in ipaddress.ip_network(cidr, strict=False):
            return True
    return False


def _resolver_cf_ray(request) -> str:
    bruto = request.META.get("HTTP_CF_RAY", "")
    remote = request.META.get("REMOTE_ADDR", "")
    if bruto and _peer_confiavel(remote) and _CF_RAY.match(bruto):
        return bruto
    return str(uuid.uuid4())


def _ip_valido(valor: str) -> bool:
    try:
        ipaddress.ip_address(valor)
    except ValueError:
        return False
    return True


def _resolver_ip(request) -> str:
    remote = request.META.get("REMOTE_ADDR", "")
    if _peer_confiavel(remote):
        # A Cloudflare põe o IP real do cliente aqui; o Traefik repassa.
        # Valida como IP antes de confiar: o valor vai para o log e a
        # auditoria, e um cabeçalho malformado (ex.: com quebra de linha) seria
        # injeção de log. Se não parecer IP, cai no peer real.
        cf = request.META.get("HTTP_CF_CONNECTING_IP", "")
        if cf and _ip_valido(cf):
            return cf
    return remote or "desconhecido"


class ObservabilidadeMiddleware:
    """Emite as duas métricas do contrato por requisição HTTP.

    Nas Tasks 2 e 3 esta mesma classe passa a capturar o Cf-Ray e a emitir a
    linha de acesso, a partir dos mesmos valores capturados aqui — sem recapturar.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.cf_ray = _resolver_cf_ray(request)
        request.client_ip = _resolver_ip(request)
        token = _CTX.set({"cf_ray": request.cf_ray, "client_ip": request.client_ip})
        inicio = time.perf_counter()
        try:
            response = self.get_response(request)
        finally:
            _CTX.reset(token)
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
            if metodo not in METODOS_CONHECIDOS:
                metodo = METODO_DESCONHECIDO
            codigo = str(response.status_code)
            REQUISICOES.labels(method=metodo, route=rota, status=codigo).inc()
            DURACAO.labels(method=metodo, route=rota).observe(duracao)

        return response
