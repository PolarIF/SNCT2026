from django.test import TestCase, override_settings


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
