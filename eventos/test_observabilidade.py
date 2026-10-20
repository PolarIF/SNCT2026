import json
import logging
from unittest import mock

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from config.observabilidade import FormatadorJSON


@override_settings(METRICS_ATIVO=True)
class ContratoDeMetricas(TestCase):
    def _raspar(self):
        return self.client.get("/metrics").content.decode()

    def test_expoe_os_nomes_do_contrato(self):
        self.client.get("/cronograma/")
        corpo = self._raspar()
        self.assertIn("http_requests_total", corpo)
        self.assertIn("http_request_duration_seconds", corpo)

    def test_rota_e_template_nao_caminho_cru(self):
        self.client.get("/trabalhos/um-slug-que-nao-existe-123/")
        corpo = self._raspar()
        # o template entra; o slug cru, não
        self.assertIn('route="/trabalhos/<slug:slug>/"', corpo.replace("\\", ""))
        self.assertNotIn("um-slug-que-nao-existe-123", corpo)

    def test_desliga_metricas_http_do_django_prometheus_mantem_banco(self):
        self.client.get("/cronograma/")
        corpo = self._raspar()
        self.assertNotIn("django_http_requests_total_by_method_total", corpo)
        self.assertIn("django_db_", corpo)  # backend de banco permanece

    def test_404_vira_rota_desconhecida(self):
        self.client.get("/essa-rota-nao-existe/")
        corpo = self._raspar()
        self.assertIn('route="<desconhecida>"', corpo)

    def test_verbo_inventado_vira_metodo_desconhecido(self):
        # O verbo HTTP vem do cliente: sem normalizar, cada verbo inventado
        # criaria uma série nova (cardinalidade sem teto). Tem de cair no balde.
        self.client.generic("VERBOINVENTADO", "/cronograma/")
        corpo = self._raspar()
        self.assertIn('method="<desconhecido>"', corpo)
        self.assertNotIn("VERBOINVENTADO", corpo)


@override_settings(METRICS_ATIVO=True, CIDRS_PROXY_CONFIAVEL=["127.0.0.1/32"])
class CorrelacaoCfRay(TestCase):
    def test_usa_cf_ray_de_proxy_confiavel(self):
        r = self.client.get("/cronograma/", HTTP_CF_RAY="8a1b2c3d4e5f6789-GRU",
                             REMOTE_ADDR="127.0.0.1")
        self.assertEqual(r.wsgi_request.cf_ray, "8a1b2c3d4e5f6789-GRU")

    def test_ignora_cf_ray_de_origem_nao_confiavel(self):
        r = self.client.get("/cronograma/", HTTP_CF_RAY="8a1b2c3d4e5f6789-GRU",
                             REMOTE_ADDR="203.0.113.9")
        self.assertNotEqual(r.wsgi_request.cf_ray, "8a1b2c3d4e5f6789-GRU")
        self.assertRegex(r.wsgi_request.cf_ray, r"^[0-9a-f-]{36}$")  # uuid

    def test_recusa_cf_ray_mal_formado_de_proxy_confiavel(self):
        r = self.client.get("/cronograma/", HTTP_CF_RAY='{"inj":1}',
                             REMOTE_ADDR="127.0.0.1")
        self.assertNotIn("inj", r.wsgi_request.cf_ray)
        self.assertRegex(r.wsgi_request.cf_ray, r"^[0-9a-f-]{36}$")

    def test_gera_uuid_quando_nao_ha_cf_ray(self):
        import uuid
        r = self.client.get("/cronograma/", REMOTE_ADDR="127.0.0.1")
        uuid.UUID(r.wsgi_request.cf_ray)  # não levanta


@override_settings(METRICS_ATIVO=True, CIDRS_PROXY_CONFIAVEL=["127.0.0.1/32"])
class ClientIpValidado(TestCase):
    def test_cf_connecting_ip_malformado_nao_vai_para_o_client_ip(self):
        # De peer confiável, mas o valor não é um IP (tentativa de injeção):
        r = self.client.get("/cronograma/",
                            HTTP_CF_CONNECTING_IP="1.2.3.4\ninjecao",
                            REMOTE_ADDR="127.0.0.1")
        self.assertNotIn("injecao", r.wsgi_request.client_ip)
        self.assertEqual(r.wsgi_request.client_ip, "127.0.0.1")  # cai no peer

    def test_cf_connecting_ip_valido_vai_para_o_client_ip(self):
        r = self.client.get("/cronograma/",
                            HTTP_CF_CONNECTING_IP="203.0.113.55",
                            REMOTE_ADDR="127.0.0.1")
        self.assertEqual(r.wsgi_request.client_ip, "203.0.113.55")


def _json_do(registro):
    """O JSON que o FormatadorJSON realmente emitiria para este registro.

    Validar por aqui (e não pelo LogRecord cru) é o ponto: um `extra` aninhado
    errado passaria no record cru e só o format() revelaria."""
    return json.loads(FormatadorJSON().format(registro))


@override_settings(METRICS_ATIVO=True, CIDRS_PROXY_CONFIAVEL=["127.0.0.1/32"])
class LinhaDeAcesso(TestCase):
    def test_linha_de_acesso_sai_em_json_com_os_campos(self):
        with self.assertLogs("snct.acesso", level="INFO") as cap:
            self.client.get("/cronograma/", HTTP_CF_RAY="8a1b2c3d4e5f6789-GRU",
                            REMOTE_ADDR="127.0.0.1")
        linha = _json_do(cap.records[-1])
        self.assertEqual(linha["extra"]["request_id"], "8a1b2c3d4e5f6789-GRU")
        self.assertEqual(linha["extra"]["route"], "/cronograma/")
        self.assertEqual(linha["extra"]["status"], 200)
        self.assertIsInstance(linha["extra"]["status"], int)
        self.assertEqual(linha["extra"]["method"], "GET")
        self.assertIn("duration_ms", linha["extra"])
        self.assertIn("client_ip", linha["extra"])

    def test_raspagem_de_rotina_nao_gera_linha_de_acesso(self):
        with self.assertLogs("snct.acesso", level="INFO") as cap:
            logging.getLogger("snct.acesso").info("sentinela")  # garante ≥1
            self.client.get("/metrics", REMOTE_ADDR="127.0.0.1")
        rotas = [_json_do(r).get("extra", {}).get("route") for r in cap.records]
        self.assertNotIn("/metrics", rotas)

    def test_raspagem_recusada_gera_linha_de_acesso(self):
        # Uma recusa (503) num caminho de infra AINDA registra — só o 200 de
        # rotina é suprimido. Força o /saude/ a falhar no banco.
        with mock.patch("eventos.views.connection.ensure_connection",
                        side_effect=Exception("banco fora")):
            with self.assertLogs("snct.acesso", level="INFO") as cap:
                self.client.get("/saude/", REMOTE_ADDR="127.0.0.1")
        linha = _json_do(cap.records[-1])
        self.assertEqual(linha["extra"]["route"], "/saude/")
        self.assertEqual(linha["extra"]["status"], 503)


@override_settings(METRICS_ATIVO=True, CIDRS_PROXY_CONFIAVEL=["127.0.0.1/32"])
class VerboCruNoLogNormalizadoNaMetrica(TestCase):
    def test_verbo_inventado_cru_no_log_mas_normalizado_na_metrica(self):
        import json
        from config.observabilidade import FormatadorJSON
        with self.assertLogs("snct.acesso", level="INFO") as cap:
            self.client.generic("VERBOX", "/cronograma/", REMOTE_ADDR="127.0.0.1")
        linha = json.loads(FormatadorJSON().format(cap.records[-1]))
        self.assertEqual(linha["extra"]["method"], "VERBOX")  # log: cru
        corpo = self.client.get("/metrics").content.decode()
        self.assertIn('method="<desconhecido>"', corpo)        # métrica: normalizado
        self.assertNotIn('method="VERBOX"', corpo)


class SaudeNaoVazaExcecao(TestCase):
    def test_503_nao_contem_o_texto_da_excecao(self):
        alvo = "eventos.views.connection.ensure_connection"
        with mock.patch(alvo, side_effect=Exception("senha=supersecreta host=10.0.0.9")):
            r = self.client.get("/saude/")
        self.assertEqual(r.status_code, 503)
        corpo = r.content.decode()
        self.assertNotIn("supersecreta", corpo)
        self.assertNotIn("10.0.0.9", corpo)

    def test_200_quando_banco_responde(self):
        r = self.client.get("/saude/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"ok\n")


@override_settings(METRICS_ATIVO=True, CIDRS_PROXY_CONFIAVEL=["127.0.0.1/32"])
class AuditoriaAdmin(TestCase):
    """Auditoria reduzida: o LogEntry do admin carrega IP e Cf-Ray no texto do
    change_message, que é o campo livre do histórico — sem subsistema novo."""

    def setUp(self):
        User.objects.create_superuser("chefe", "c@x.com", "segredo123")
        self.client.force_login(User.objects.get(username="chefe"))

    def test_log_entry_registra_ip_e_cf_ray(self):
        self.client.post(
            "/admin/eventos/area/add/",
            {"nome": "Robótica", "slug": "robotica", "ativo": "on",
             "gestores": [], "link_inscricao": ""},
            HTTP_CF_RAY="8a1b2c3d4e5f6789-GRU", REMOTE_ADDR="127.0.0.1",
        )
        entrada = LogEntry.objects.latest("id")
        self.assertIn("8a1b2c3d4e5f6789-GRU", entrada.change_message)
        self.assertIn("127.0.0.1", entrada.change_message)
