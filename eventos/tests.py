"""Testes do que não pode dar errado: quem pode mexer em quê.

Todo teste de permissão aqui bate direto na URL, com POST de verdade. Esconder
o botão na tela não conta — o que conta é o servidor recusar.
"""

import pathlib
import shutil
import tempfile
from datetime import date, time

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse, reverse_lazy

from .models import Anexo, Area, Cartao, Etapa, Evento, Horario, LinkDeEnvio, Submissao


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        # As migrações semeiam as áreas reais da semana e os cartões da página
        # inicial. Os testes montam o próprio cenário, então começam do zero
        # para não depender delas. Os cartões saem primeiro: a área é
        # PROTECT, e é para ser assim — apagar um curso não pode levar junto,
        # em silêncio, o cartão que fala dele.
        Cartao.objects.all().delete()
        Area.objects.all().delete()

        # As duas mostras ficam — são linhas fixas, criadas pela migração —,
        # mas sem as datas que a migração copiou do HTML antigo: cada teste
        # diz o que a mostra tem. O que a migração semeia é testado à parte,
        # em MostrasSemeadas.
        Etapa.objects.all().delete()
        LinkDeEnvio.objects.all().delete()
        cls.cientifica = Submissao.objects.get(slug="mostra-cientifica")
        cls.empreendedora = Submissao.objects.get(slug="mostra-empreendedora-e-tecnologica")

        cls.ads = Area.objects.create(nome="ADS", slug="ads")
        cls.info = Area.objects.create(nome="Informática", slug="informatica")
        cls.eletro = Area.objects.create(nome="Eletrotécnica", slug="eletrotecnica")

        cls.admin = User.objects.create_superuser("admin", password="senha-de-teste-123")

        # coord_ads cuida de uma área
        cls.coord_ads = User.objects.create_user("coord_ads", password="senha-de-teste-123")
        cls.ads.gestores.add(cls.coord_ads)

        # coord_duas cuida de duas
        cls.coord_duas = User.objects.create_user("coord_duas", password="senha-de-teste-123")
        cls.info.gestores.add(cls.coord_duas)
        cls.eletro.gestores.add(cls.coord_duas)

        # conta desativada
        cls.inativo = User.objects.create_user(
            "inativo", password="senha-de-teste-123", is_active=False
        )
        cls.ads.gestores.add(cls.inativo)

        # sem nenhuma área
        cls.sem_area = User.objects.create_user("sem_area", password="senha-de-teste-123")

        cls.ev_ads = Evento.objects.create(
            titulo="Palestra sobre Inteligência Artificial",
            local="Auditório",
            area=cls.ads,
        )
        Horario.objects.create(
            evento=cls.ev_ads, data=date(2026, 10, 28), hora_inicio=time(14, 0)
        )
        cls.ev_info = Evento.objects.create(
            titulo="Workshop de Flutter",
            local="Laboratório 03",
            area=cls.info,
        )
        Horario.objects.create(
            evento=cls.ev_info, data=date(2026, 10, 29), hora_inicio=time(16, 0)
        )

    def entrar(self, usuario):
        ok = self.client.login(username=usuario, password="senha-de-teste-123")
        self.assertTrue(ok, f"{usuario} deveria conseguir entrar")

    def abrir(self, mostra=None, url="https://forms.exemplo.invalid/trabalhos", prazo=None):
        """Abre a submissão de uma mostra (a Científica, se nenhuma for dita)."""
        mostra = mostra or self.cientifica
        mostra.aberta = True
        mostra.prazo = prazo
        mostra.save()
        LinkDeEnvio.objects.create(submissao=mostra, rotulo="Enviar meu trabalho", url=url)
        return mostra

    def dados(self, **troca):
        """O POST do formulário de evento, com o formset de horários junto.

        O formset exige os campos de gestão (TOTAL_FORMS e companhia); sem
        eles o Django recusa o envio antes de olhar qualquer campo, e o teste
        falharia por um motivo que nada tem a ver com o que ele mede.
        """
        base = {
            "titulo": "Evento de teste",
            "local": "Sala 1",
            "descricao": "",
            "horarios-TOTAL_FORMS": "1",
            "horarios-INITIAL_FORMS": "0",
            "horarios-MIN_NUM_FORMS": "0",
            "horarios-MAX_NUM_FORMS": "1000",
            "horarios-0-data": "2026-10-30",
            "horarios-0-hora_inicio": "09:00",
            "horarios-0-hora_fim": "",
        }
        base.update(troca)
        return base


class SitePublico(Base):
    def test_home_abre_sem_login(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Semana Nacional de Ciência e Tecnologia")

    def test_cronograma_abre_sem_login_e_mostra_eventos(self):
        r = self.client.get(reverse("cronograma"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Palestra sobre Inteligência Artificial")
        self.assertContains(r, "Workshop de Flutter")

    def test_cronograma_filtra_por_area(self):
        r = self.client.get(reverse("cronograma"), {"area": "ads"})
        self.assertContains(r, "Palestra sobre Inteligência Artificial")
        self.assertNotContains(r, "Workshop de Flutter")

    def test_filtro_de_area_sem_evento_nao_mostra_o_cronograma_inteiro(self):
        """Os cartões da home linkam para áreas que ainda não têm atividade."""
        r = self.client.get(reverse("cronograma"), {"area": "eletrotecnica"})
        self.assertContains(r, "Nenhuma atividade")
        self.assertContains(r, "Eletrotécnica")
        self.assertNotContains(r, "Palestra sobre Inteligência Artificial")
        self.assertNotContains(r, "Workshop de Flutter")

    def test_filtro_de_area_desativada_e_ignorado(self):
        self.eletro.ativo = False
        self.eletro.save()
        r = self.client.get(reverse("cronograma"), {"area": "eletrotecnica"})
        self.assertContains(r, "Palestra sobre Inteligência Artificial")

    def test_slug_inexistente_mostra_tudo(self):
        r = self.client.get(reverse("cronograma"), {"area": "nao-existe"})
        self.assertContains(r, "Palestra sobre Inteligência Artificial")
        self.assertContains(r, "Workshop de Flutter")

    def test_cartoes_da_home_apontam_para_o_cronograma_da_propria_area(self):
        for area in [self.ads, self.info, self.eletro]:
            Cartao.objects.create(area=area, titulo=f"Cartão {area.nome}", descricao="x")

        r = self.client.get(reverse("home"))
        for area in [self.ads, self.info, self.eletro]:
            with self.subTest(slug=area.slug):
                self.assertContains(r, f'href="/cronograma/?area={area.slug}"')

    def test_area_desativada_nao_aparece_no_publico(self):
        self.ads.ativo = False
        self.ads.save()
        r = self.client.get(reverse("cronograma"))
        self.assertNotContains(r, "Palestra sobre Inteligência Artificial")

    def test_alteracao_no_painel_aparece_no_cronograma(self):
        self.entrar("coord_ads")
        self.client.post(
            reverse("painel:editar", args=[self.ev_ads.pk]),
            self.dados(
                titulo=self.ev_ads.titulo,
                area=self.ads.pk,
                **{
                    # editar mexe num horário que já existe: o formset precisa
                    # do id dele, senão cria um segundo em vez de alterar
                    "horarios-INITIAL_FORMS": "1",
                    "horarios-0-id": str(self.ev_ads.horarios.get().pk),
                    "horarios-0-data": "2026-10-28",
                    "horarios-0-hora_inicio": "15:00",
                },
            ),
        )
        self.client.logout()

        r = self.client.get(reverse("cronograma"))
        self.assertContains(r, "15:00")
        self.assertNotContains(r, "14:00")


class InscricaoNaHome(Base):
    """A inscrição é dado, não HTML: a organização abre e fecha pelo /admin/."""

    def setUp(self):
        # o estado da inscrição aparece no cartão daquela área
        self.cieec = Area.objects.create(nome="CIEEC", slug="cieec")
        Cartao.objects.create(
            area=self.cieec, titulo="Feira do CIEEC", descricao="Uma feira."
        )

    def test_sem_link_mostra_em_breve(self):
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Inscrições em breve")

    def test_com_link_e_aberta_mostra_o_botao(self):
        self.cieec.inscricoes_abertas = True
        self.cieec.link_inscricao = "https://suap.ifro.edu.br/eventos/inscricao/1/999/"
        self.cieec.save()

        r = self.client.get(reverse("home"))
        self.assertContains(r, "https://suap.ifro.edu.br/eventos/inscricao/1/999/")
        self.assertContains(r, "Inscreva-se")
        self.assertContains(r, "Inscrições abertas")

    def test_aberta_sem_link_nao_gera_botao_vazio(self):
        self.cieec.inscricoes_abertas = True
        self.cieec.save()

        r = self.client.get(reverse("home"))
        self.assertContains(r, "Inscrições abertas")     # o selo aparece
        self.assertNotContains(r, 'href=""')             # mas sem botão quebrado
        self.assertIs(self.cieec.mostra_botao_inscricao, False)

    def test_link_sem_estar_aberta_nao_vaza(self):
        self.cieec.link_inscricao = "https://suap.ifro.edu.br/eventos/inscricao/1/999/"
        self.cieec.save()

        r = self.client.get(reverse("home"))
        self.assertNotContains(r, "inscricao/1/999")
        self.assertNotContains(r, "Inscrições abertas")

    def test_area_desativada_nao_mostra_inscricao(self):
        self.cieec.inscricoes_abertas = True
        self.cieec.link_inscricao = "https://suap.ifro.edu.br/eventos/inscricao/1/999/"
        self.cieec.ativo = False
        self.cieec.save()

        r = self.client.get(reverse("home"))
        self.assertNotContains(r, "inscricao/1/999")


class InscricaoPeloPainel(Base):
    """Quem abre e fecha a inscrição é a coordenação, no painel."""

    def url(self, area):
        return reverse("painel:inscricao", args=[area.slug])

    def test_coordenacao_abre_a_inscricao_da_propria_area(self):
        self.entrar("coord_ads")
        r = self.client.post(
            self.url(self.ads),
            {"inscricoes_abertas": "on",
             "link_inscricao": "https://suap.ifro.edu.br/eventos/inscricao/1/777/"},
        )
        self.assertRedirects(r, reverse("painel:lista"))

        self.ads.refresh_from_db()
        self.assertTrue(self.ads.inscricoes_abertas)
        self.assertTrue(self.ads.mostra_botao_inscricao)

    def test_coordenacao_fecha_a_inscricao(self):
        self.ads.inscricoes_abertas = True
        self.ads.link_inscricao = "https://suap.ifro.edu.br/eventos/inscricao/1/777/"
        self.ads.save()

        self.entrar("coord_ads")
        self.client.post(self.url(self.ads), {"link_inscricao": self.ads.link_inscricao})

        self.ads.refresh_from_db()
        self.assertFalse(self.ads.inscricoes_abertas)

    def test_link_sem_esquema_vira_https(self):
        self.entrar("coord_ads")
        self.client.post(
            self.url(self.ads),
            {"inscricoes_abertas": "on", "link_inscricao": "suap.ifro.edu.br/eventos/inscricao/1/9/"},
        )
        self.ads.refresh_from_db()
        self.assertTrue(self.ads.link_inscricao.startswith("https://"))

    def test_link_invalido_e_recusado(self):
        self.entrar("coord_ads")
        r = self.client.post(self.url(self.ads), {"link_inscricao": "isso não é um link"})
        self.assertEqual(r.status_code, 200)
        self.ads.refresh_from_db()
        self.assertEqual(self.ads.link_inscricao, "")

    # ---------------------------------------------------------- o que não pode

    def test_nao_abre_a_tela_de_area_alheia(self):
        self.entrar("coord_ads")
        self.assertEqual(self.client.get(self.url(self.info)).status_code, 404)

    def test_nao_altera_area_alheia_por_post_direto(self):
        self.entrar("coord_ads")
        r = self.client.post(
            self.url(self.info),
            {"inscricoes_abertas": "on", "link_inscricao": "https://exemplo.invalid/x/"},
        )
        self.assertEqual(r.status_code, 404)
        self.info.refresh_from_db()
        self.assertFalse(self.info.inscricoes_abertas)
        self.assertEqual(self.info.link_inscricao, "")

    def test_exige_login(self):
        self.assertEqual(self.client.get(self.url(self.ads)).status_code, 302)

    def test_administrador_altera_qualquer_area(self):
        self.entrar("admin")
        r = self.client.post(
            self.url(self.eletro),
            {"inscricoes_abertas": "on",
             "link_inscricao": "https://suap.ifro.edu.br/eventos/inscricao/1/555/"},
        )
        self.assertRedirects(r, reverse("painel:lista"))
        self.eletro.refresh_from_db()
        self.assertTrue(self.eletro.mostra_botao_inscricao)

    def test_a_lista_do_painel_mostra_o_estado_e_o_link_de_alterar(self):
        self.entrar("coord_ads")
        r = self.client.get(reverse("painel:lista"))
        self.assertContains(r, "estado--breve")
        self.assertContains(r, self.url(self.ads))
        self.assertNotContains(r, self.url(self.info))

    def test_a_lista_mostra_o_estado_certo_em_cada_caso(self):
        self.entrar("coord_ads")

        self.ads.inscricoes_abertas = True
        self.ads.save()
        r = self.client.get(reverse("painel:lista"))
        self.assertContains(r, "estado--falta")
        self.assertContains(r, "Nenhum botão aparece no site sem o link")

        self.ads.link_inscricao = "https://suap.ifro.edu.br/eventos/inscricao/1/1/"
        self.ads.save()
        r = self.client.get(reverse("painel:lista"))
        self.assertContains(r, "estado--aberta")
        self.assertNotContains(r, "Nenhum botão aparece")

    def test_abrir_no_painel_muda_a_pagina_inicial(self):
        """O ciclo inteiro: coordenação abre no painel, visitante vê o botão."""
        cieec = Area.objects.create(nome="CIEEC", slug="cieec")
        cieec.gestores.add(self.coord_ads)
        Cartao.objects.create(area=cieec, titulo="Feira do CIEEC", descricao="Uma feira.")

        self.entrar("coord_ads")
        self.client.post(
            reverse("painel:inscricao", args=["cieec"]),
            {"inscricoes_abertas": "on",
             "link_inscricao": "https://suap.ifro.edu.br/eventos/inscricao/1/321/"},
        )
        self.client.logout()

        r = self.client.get(reverse("home"))
        self.assertContains(r, "inscricao/1/321/")
        self.assertContains(r, "Inscreva-se")


class SubmissaoNaHome(Base):
    """A submissão é uma por mostra, e é dado — não HTML."""

    def test_fechada_mostra_em_breve_e_nao_vaza_link(self):
        LinkDeEnvio.objects.create(
            submissao=self.cientifica,
            rotulo="Enviar",
            url="https://forms.exemplo.invalid/trabalhos",
        )

        r = self.client.get(reverse("home"))
        self.assertContains(r, "Em breve")
        self.assertNotContains(r, "forms.exemplo.invalid")
        self.assertNotContains(r, "Enviar meu trabalho")

    def test_aberta_com_link_mostra_o_botao(self):
        self.abrir()

        r = self.client.get(reverse("home"))
        self.assertContains(r, "Enviar meu trabalho")
        # o botão leva à mostra na página de submissão, e não direto ao formulário
        self.assertContains(r, f'href="{reverse("trabalhos")}#mostra-cientifica"')
        self.assertNotContains(r, "https://forms.exemplo.invalid/trabalhos")
        # sem prazo marcado, o lugar grande do cartão diz o estado
        self.assertContains(r, "Aberta")

    def test_aberta_sem_link_nao_gera_botao_vazio(self):
        self.cientifica.aberta = True
        self.cientifica.save()

        r = self.client.get(reverse("home"))
        self.assertContains(r, "Em breve")
        self.assertNotContains(r, "Enviar meu trabalho")
        self.assertNotContains(r, 'href=""')
        self.assertIs(self.cientifica.mostra_botao, False)

    def test_prazo_so_aparece_quando_preenchido(self):
        self.abrir()
        self.assertNotContains(self.client.get(reverse("home")), "Prazo de envio")

        self.cientifica.prazo = date(2026, 10, 10)
        self.cientifica.save()
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Prazo de envio")
        self.assertContains(r, "de outubro")

    def test_as_duas_mostras_tem_cartao_proprio(self):
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Mostra Científica")
        self.assertContains(r, "Mostra Empreendedora e Tecnológica")
        self.assertContains(r, "São 2 mostras")

    def test_uma_mostra_aberta_nao_abre_a_outra(self):
        self.abrir(self.cientifica)

        html = self.client.get(reverse("home")).content.decode()
        self.assertEqual(html.count("Enviar meu trabalho"), 1)
        # o botão que existe é o da Científica, e o cartão da Empreendedora
        # continua dizendo "em breve"
        cartao_empreendedora = html[html.index("Mostra Empreendedora e Tecnológica</h3>"):]
        self.assertNotIn("Enviar meu trabalho", cartao_empreendedora)
        self.assertIn("Em breve", cartao_empreendedora)

    def test_cada_cartao_leva_a_propria_mostra(self):
        self.abrir(self.cientifica)
        self.abrir(self.empreendedora, url="https://forms.exemplo.invalid/empreende")

        r = self.client.get(reverse("home"))
        self.assertContains(r, f'href="{reverse("trabalhos")}#mostra-cientifica"')
        self.assertContains(
            r, f'href="{reverse("trabalhos")}#mostra-empreendedora-e-tecnologica"'
        )

    def test_o_texto_da_mostra_vem_do_painel(self):
        self.empreendedora.resumo = "Projetos de **inovação** e <script>x</script>."
        self.empreendedora.save()

        r = self.client.get(reverse("home"))
        self.assertContains(r, "<b>inovação</b>")
        self.assertNotContains(r, "<script>x</script>")

    def test_a_secao_aparece_antes_da_programacao(self):
        # a submissão é a primeira seção da página, e é isso que o pedido era
        html = self.client.get(reverse("home")).content.decode()
        self.assertLess(html.index('id="trabalhos"'), html.index('id="programacao"'))

    def test_como_se_inscrever_fica_acima_dos_cartoes_e_sempre_aberto(self):
        html = self.client.get(reverse("home")).content.decode()
        self.assertIn('id="inscrever"', html)
        self.assertIn("Como se inscrever", html)
        # acima da grade, e não recolhido num <details>
        self.assertLess(html.index('id="inscrever"'), html.index('class="grade-eventos"'))
        self.assertIn("Escolha o evento", html)


class SubmissaoPeloPainel(Base):
    """Quem mexe na submissão é a organização: ela vale para a semana inteira."""

    url = reverse_lazy("painel:submissao", args=["mostra-cientifica"])

    def dados(self, links=(), etapas=(), **troca):
        """O POST da tela da mostra, com os dois formsets e os campos de gestão.

        `links` é uma lista de (texto do botão, endereço); `etapas`, de
        (etapa, início, fim). Linhas novas só — os testes partem de mostra
        sem link e sem data.
        """
        base = {
            "nome": "Mostra Científica",
            "resumo": "",
            "prazo": "",
            "links-TOTAL_FORMS": str(len(links)),
            "links-INITIAL_FORMS": "0",
            "links-MIN_NUM_FORMS": "0",
            "links-MAX_NUM_FORMS": "1000",
            "etapas-TOTAL_FORMS": str(len(etapas)),
            "etapas-INITIAL_FORMS": "0",
            "etapas-MIN_NUM_FORMS": "0",
            "etapas-MAX_NUM_FORMS": "1000",
        }
        for i, (rotulo, url) in enumerate(links):
            base[f"links-{i}-rotulo"] = rotulo
            base[f"links-{i}-url"] = url
        for i, (titulo, inicio, fim) in enumerate(etapas):
            base[f"etapas-{i}-titulo"] = titulo
            base[f"etapas-{i}-inicio"] = inicio
            base[f"etapas-{i}-fim"] = fim
            base[f"etapas-{i}-descricao"] = ""
        base.update(troca)
        return base

    def recarregar(self):
        return Submissao.objects.get(pk=self.cientifica.pk)

    def test_administrador_abre_a_submissao(self):
        self.entrar("admin")
        r = self.client.post(
            self.url,
            self.dados(
                aberta="on",
                links=[("Enviar meu trabalho", "https://forms.exemplo.invalid/trabalhos")],
            ),
        )
        self.assertEqual(r.status_code, 302)

        s = self.recarregar()
        self.assertTrue(s.aberta)
        self.assertEqual(
            [l.url for l in s.links.all()], ["https://forms.exemplo.invalid/trabalhos"]
        )
        self.assertTrue(s.mostra_botao)

    def test_link_sem_esquema_vira_https(self):
        self.entrar("admin")
        self.client.post(
            self.url,
            self.dados(aberta="on", links=[("Enviar", "forms.exemplo.invalid/trabalhos")]),
        )
        self.assertEqual(
            self.recarregar().links.get().url, "https://forms.exemplo.invalid/trabalhos"
        )

    def test_link_invalido_e_recusado(self):
        self.entrar("admin")
        r = self.client.post(
            self.url, self.dados(aberta="on", links=[("Enviar", "isto não é um link")])
        )
        self.assertEqual(r.status_code, 200)
        # nada é gravado pela metade: nem a mostra abre, nem o link entra
        self.assertFalse(self.recarregar().aberta)
        self.assertFalse(LinkDeEnvio.objects.exists())

    def test_linha_vazia_e_ignorada(self):
        self.entrar("admin")
        r = self.client.post(
            self.url,
            self.dados(aberta="on", links=[("Enviar", "https://forms.exemplo.invalid/a"), ("", "")]),
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.recarregar().links.count(), 1)

    def test_link_sem_texto_do_botao_e_recusado(self):
        self.entrar("admin")
        r = self.client.post(
            self.url, self.dados(links=[("", "https://forms.exemplo.invalid/a")])
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(LinkDeEnvio.objects.exists())

    def test_dois_links_viram_dois_botoes(self):
        # o caso da Empreendedora: um formulário para estudantes, outro para
        # professores
        self.entrar("admin")
        url = reverse("painel:submissao", args=[self.empreendedora.slug])
        r = self.client.post(
            url,
            self.dados(
                nome="Mostra Empreendedora e Tecnológica",
                aberta="on",
                links=[
                    ("Sou estudante", "https://forms.exemplo.invalid/estudantes"),
                    ("Sou professor", "https://forms.exemplo.invalid/professores"),
                ],
            ),
        )
        self.assertEqual(r.status_code, 302)

        html = self.client.get(reverse("trabalhos")).content.decode()
        self.assertLess(html.index("Sou estudante"), html.index("Sou professor"))
        self.assertIn("https://forms.exemplo.invalid/estudantes", html)
        self.assertIn("https://forms.exemplo.invalid/professores", html)
        # e a Científica, que ninguém abriu, continua sem botão
        self.assertFalse(self.recarregar().mostra_botao)

    def test_remover_o_unico_link_tira_o_botao(self):
        link = LinkDeEnvio.objects.create(
            submissao=self.cientifica, rotulo="Enviar", url="https://forms.exemplo.invalid/a"
        )
        self.entrar("admin")
        dados = self.dados(aberta="on")
        dados.update(
            {
                "links-TOTAL_FORMS": "1",
                "links-INITIAL_FORMS": "1",
                "links-0-id": str(link.pk),
                "links-0-rotulo": "Enviar",
                "links-0-url": "https://forms.exemplo.invalid/a",
                "links-0-DELETE": "on",
            }
        )
        self.assertEqual(self.client.post(self.url, dados).status_code, 302)
        self.assertFalse(LinkDeEnvio.objects.exists())
        self.assertIn("sem link", self.recarregar().situacao)

    def test_as_datas_saem_em_ordem_de_data(self):
        self.entrar("admin")
        r = self.client.post(
            self.url,
            self.dados(
                etapas=[
                    ("Resultado final", "2026-10-22", ""),
                    ("Submissão", "2026-09-24", "2026-10-12"),
                ]
            ),
        )
        self.assertEqual(r.status_code, 302)

        html = self.client.get(reverse("trabalhos")).content.decode()
        self.assertLess(html.index("Submissão</h4>"), html.index("Resultado final</h4>"))
        self.assertIn('<time datetime="2026-09-24">24/09</time>', html)

    def test_etapa_que_termina_antes_de_comecar_e_recusada(self):
        self.entrar("admin")
        r = self.client.post(
            self.url, self.dados(etapas=[("Avaliação", "2026-10-15", "2026-10-01")])
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Etapa.objects.exists())

    def test_mostra_sem_datas_oferece_o_cronograma_inteiro(self):
        self.entrar("admin")
        r = self.client.get(self.url)
        self.assertEqual(r.context["etapas"].total_form_count(), 4)

        Etapa.objects.create(submissao=self.cientifica, titulo="Envio", inicio=date(2026, 10, 1))
        r = self.client.get(self.url)
        self.assertEqual(r.context["etapas"].total_form_count(), 2)

    def test_mostra_que_nao_existe_da_404(self):
        self.entrar("admin")
        url = reverse("painel:submissao", args=["mostra-que-nao-existe"])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_coordenacao_nao_abre_a_tela(self):
        self.entrar("coord_ads")
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_coordenacao_nao_altera_por_post_direto(self):
        self.entrar("coord_ads")
        r = self.client.post(
            self.url,
            self.dados(aberta="on", links=[("Enviar", "https://invasao.exemplo.invalid/")]),
        )
        self.assertEqual(r.status_code, 404)
        self.assertFalse(self.recarregar().aberta)
        self.assertFalse(LinkDeEnvio.objects.exists())

    def test_o_bloco_so_aparece_para_o_administrador(self):
        self.entrar("admin")
        r = self.client.get(reverse("painel:lista"))
        self.assertContains(r, "Submissão de trabalhos")
        self.assertContains(r, "Mostra Empreendedora e Tecnológica")

        self.client.logout()
        self.entrar("coord_ads")
        r = self.client.get(reverse("painel:lista"))
        self.assertNotContains(r, "Submissão de trabalhos")

    def test_abrir_no_painel_muda_a_pagina_inicial(self):
        self.assertNotContains(self.client.get(reverse("home")), "Enviar meu trabalho")

        self.entrar("admin")
        self.client.post(
            self.url,
            self.dados(
                aberta="on",
                prazo="2026-10-10",
                links=[("Enviar meu trabalho", "https://forms.exemplo.invalid/t")],
            ),
        )

        self.client.logout()
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Enviar meu trabalho")
        self.assertContains(r, "Prazo de envio")
        self.assertContains(r, "de outubro")
        # o formulário em si está na página de submissão
        self.assertContains(
            self.client.get(reverse("trabalhos")), "https://forms.exemplo.invalid/t"
        )


class CartoesNaHome(Base):
    """Os cartões da página inicial são dados, e o texto sai escapado."""

    def setUp(self):
        self.cartao = Cartao.objects.create(
            area=self.ads,
            trilha="Abertura oficial",
            titulo="Abertura no laboratório",
            coordenacao="Comissão organizadora",
            descricao="Cerimônia de abertura no Campus.",
            programacao_rotulo="28/10",
            programacao="Cerimônia\nMostras dos cursos\n\n  ",
            ordem=0,
        )

    def test_o_cartao_aparece_com_o_que_foi_cadastrado(self):
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Abertura no laboratório")
        self.assertContains(r, "Abertura oficial")
        self.assertContains(r, "Comissão organizadora")
        self.assertContains(r, "Programação · 28/10")
        self.assertContains(r, "<li>Cerimônia</li>", html=False)

    def test_linhas_vazias_da_programacao_nao_viram_item(self):
        self.assertEqual(self.cartao.itens_programacao, ["Cerimônia", "Mostras dos cursos"])

    def test_sem_responsavel_mostra_a_confirmar(self):
        self.assertContains(self.client.get(reverse("home")), "a confirmar")

        self.cartao.responsavel = "Eudóxia Moura"
        self.cartao.save()
        r = self.client.get(reverse("home"))
        self.assertContains(r, "Eudóxia Moura")

    def test_etiqueta_em_branco_usa_o_nome_do_curso(self):
        self.cartao.trilha = ""
        self.cartao.save()
        self.assertEqual(self.cartao.etiqueta, "ADS")
        self.assertContains(self.client.get(reverse("home")), "ADS")

    def test_cartao_despublicado_some_do_site(self):
        self.cartao.publicado = False
        self.cartao.save()
        self.assertNotContains(self.client.get(reverse("home")), "Abertura no laboratório")

    def test_cartao_de_area_desativada_some_do_site(self):
        self.ads.ativo = False
        self.ads.save()
        self.assertNotContains(self.client.get(reverse("home")), "Abertura no laboratório")

    def test_html_digitado_no_painel_sai_como_texto(self):
        self.cartao.descricao = '<script>alert(1)</script> e <b>negrito</b>'
        self.cartao.save()
        r = self.client.get(reverse("home"))
        self.assertNotContains(r, "<script>")
        self.assertNotContains(r, "<b>negrito</b>")
        self.assertContains(r, "&lt;script&gt;")

    def test_a_palavra_campus_sai_em_italico(self):
        self.assertContains(self.client.get(reverse("home")), "no <i>Campus</i>")

    def test_ver_horarios_leva_ao_cronograma_por_padrao(self):
        self.assertEqual(self.cartao.url_horarios, "/cronograma/?area=ads")
        self.assertIs(self.cartao.horarios_fora, False)

        r = self.client.get(reverse("home"))
        self.assertContains(r, 'href="/cronograma/?area=ads"')

    def test_link_proprio_tira_o_ver_horarios_do_site(self):
        # um curso que publica a programação em página própria
        self.cartao.link_horarios = "https://exemplo.invalid/horarios/"
        self.cartao.save()

        self.assertEqual(self.cartao.url_horarios, "https://exemplo.invalid/horarios/")
        self.assertIs(self.cartao.horarios_fora, True)

        r = self.client.get(reverse("home"))
        self.assertContains(r, 'href="https://exemplo.invalid/horarios/"')
        self.assertNotContains(r, 'href="/cronograma/?area=ads"')
        # link para fora abre em outra aba, e sem passar o referenciador
        self.assertContains(r, 'rel="noopener"')

    def test_o_link_proprio_e_so_daquele_cartao(self):
        self.cartao.link_horarios = "https://exemplo.invalid/horarios/"
        self.cartao.save()
        outro = Cartao.objects.create(area=self.info, titulo="Outro", descricao="x")

        r = self.client.get(reverse("home"))
        self.assertContains(r, 'href="https://exemplo.invalid/horarios/"')
        self.assertContains(r, f'href="/cronograma/?area={outro.area.slug}"')

    def test_a_inscricao_continua_vindo_da_area(self):
        # o cartão não guarda link de inscrição: quem manda nisso é a área
        self.ads.inscricoes_abertas = True
        self.ads.link_inscricao = "https://suap.exemplo.invalid/1/"
        self.ads.save()

        r = self.client.get(reverse("home"))
        self.assertContains(r, "https://suap.exemplo.invalid/1/")
        self.assertContains(r, "Inscreva-se")

    def test_ordem_manda_na_sequencia(self):
        Cartao.objects.create(
            area=self.info, titulo="Primeiro de todos", descricao="x", ordem=-0
        )
        segundo = Cartao.objects.get(pk=self.cartao.pk)
        segundo.ordem = 5
        segundo.save()

        html = self.client.get(reverse("home")).content.decode()
        self.assertLess(html.index("Primeiro de todos"), html.index("Abertura no laboratório"))


class CartoesPeloPainel(Base):
    """Só o administrador edita os cartões — no GET e no POST."""

    def setUp(self):
        self.cartao = Cartao.objects.create(
            area=self.ads, titulo="Cartão de teste", descricao="Texto.", ordem=0
        )

    def dados_do_cartao(self, **troca):
        base = {
            "titulo": "Cartão de teste",
            "area": self.ads.pk,
            "trilha": "",
            "responsavel": "",
            "coordenacao": "",
            "descricao": "Texto.",
            "programacao_rotulo": "",
            "programacao": "",
            "link_horarios": "",
            "ordem": 0,
            "publicado": "on",
        }
        base.update(troca)
        return base

    def test_administrador_cria_edita_e_exclui(self):
        self.entrar("admin")

        r = self.client.post(
            reverse("painel:cartao_novo"), self.dados_do_cartao(titulo="Novo cartão")
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Cartao.objects.filter(titulo="Novo cartão").exists())

        r = self.client.post(
            reverse("painel:cartao_editar", args=[self.cartao.pk]),
            self.dados_do_cartao(titulo="Título trocado"),
        )
        self.assertEqual(r.status_code, 302)
        self.cartao.refresh_from_db()
        self.assertEqual(self.cartao.titulo, "Título trocado")

        r = self.client.post(reverse("painel:cartao_excluir", args=[self.cartao.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Cartao.objects.filter(pk=self.cartao.pk).exists())

    def test_coordenacao_nao_abre_nenhuma_das_telas(self):
        self.entrar("coord_ads")
        urls = [
            reverse("painel:cartoes"),
            reverse("painel:cartao_novo"),
            reverse("painel:cartao_editar", args=[self.cartao.pk]),
            reverse("painel:cartao_excluir", args=[self.cartao.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_coordenacao_nao_edita_por_post_direto(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:cartao_editar", args=[self.cartao.pk]),
            self.dados_do_cartao(titulo="Invadido"),
        )
        self.assertEqual(r.status_code, 404)
        self.cartao.refresh_from_db()
        self.assertEqual(self.cartao.titulo, "Cartão de teste")

    def test_coordenacao_nao_exclui_por_post_direto(self):
        self.entrar("coord_ads")
        r = self.client.post(reverse("painel:cartao_excluir", args=[self.cartao.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Cartao.objects.filter(pk=self.cartao.pk).exists())

    def test_get_nao_exclui(self):
        self.entrar("admin")
        self.client.get(reverse("painel:cartao_excluir", args=[self.cartao.pk]))
        self.assertTrue(Cartao.objects.filter(pk=self.cartao.pk).exists())

    def test_o_atalho_so_aparece_para_o_administrador(self):
        self.entrar("admin")
        self.assertContains(self.client.get(reverse("painel:lista")), "Cartões da página inicial")

        self.client.logout()
        self.entrar("coord_ads")
        r = self.client.get(reverse("painel:lista"))
        self.assertNotContains(r, "Cartões da página inicial")

    def test_editar_no_painel_muda_a_pagina_inicial(self):
        self.entrar("admin")
        self.client.post(
            reverse("painel:cartao_editar", args=[self.cartao.pk]),
            self.dados_do_cartao(titulo="Aparece no site", descricao="Descrição nova."),
        )
        self.client.logout()

        r = self.client.get(reverse("home"))
        self.assertContains(r, "Aparece no site")
        self.assertContains(r, "Descrição nova.")


# MEDIA_ROOT próprio: teste que envia arquivo não escreve na pasta de verdade.
MIDIA_DE_TESTE = tempfile.mkdtemp(prefix="snct-teste-midia-")


@override_settings(MEDIA_ROOT=MIDIA_DE_TESTE)
class PaginaDeTrabalhos(Base):
    """A página de submissão: os documentos primeiro, o envio no fim."""

    url = reverse_lazy("trabalhos")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MIDIA_DE_TESTE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        # A migração 0009 semeia os três documentos anunciados; estes testes
        # montam o próprio cenário. O delete volta atrás no fim de cada teste.
        Anexo.objects.all().delete()

    def test_a_pagina_existe_mesmo_sem_nada_publicado(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        # um aviso por mostra, e não três caixas vazias seguidas
        self.assertContains(r, "Esta mostra ainda vai abrir", count=2)

    def test_fechada_nao_vaza_o_link_do_formulario(self):
        LinkDeEnvio.objects.create(
            submissao=self.cientifica, rotulo="Enviar", url="https://forms.exemplo.invalid/trabalhos"
        )
        Anexo.objects.create(
            submissao=self.cientifica, titulo="Regulamento", link="https://exemplo.invalid/reg.pdf"
        )

        r = self.client.get(self.url)
        self.assertNotContains(r, "forms.exemplo.invalid")
        self.assertContains(r, "abre em breve")

    def test_as_duas_mostras_estao_na_pagina_em_ordem(self):
        html = self.client.get(self.url).content.decode()
        self.assertLess(
            html.index('id="mostra-cientifica"'),
            html.index('id="mostra-empreendedora-e-tecnologica"'),
        )
        # e os atalhos do topo apontam para cada uma
        self.assertIn('href="#mostra-cientifica"', html)
        self.assertIn('href="#mostra-empreendedora-e-tecnologica"', html)

    def test_cada_documento_fica_na_sua_mostra(self):
        Anexo.objects.create(
            submissao=self.cientifica, titulo="Regulamento científico",
            link="https://exemplo.invalid/c.pdf",
        )
        Anexo.objects.create(
            submissao=self.empreendedora, titulo="Regulamento empreendedor",
            link="https://exemplo.invalid/e.pdf",
        )

        html = self.client.get(self.url).content.decode()
        divisa = html.index('id="mostra-empreendedora-e-tecnologica"')
        self.assertLess(html.index("Regulamento científico"), divisa)
        self.assertGreater(html.index("Regulamento empreendedor"), divisa)

    def test_uma_mostra_aberta_nao_vaza_o_link_da_outra(self):
        self.abrir(self.empreendedora, url="https://forms.exemplo.invalid/empreende")
        LinkDeEnvio.objects.create(
            submissao=self.cientifica, rotulo="Enviar", url="https://forms.exemplo.invalid/ciencia"
        )

        r = self.client.get(self.url)
        self.assertContains(r, "https://forms.exemplo.invalid/empreende")
        self.assertNotContains(r, "https://forms.exemplo.invalid/ciencia")

    def test_mostra_sem_datas_avisa_que_vao_ser_divulgadas(self):
        Anexo.objects.create(
            submissao=self.cientifica, titulo="Regulamento", link="https://exemplo.invalid/r.pdf"
        )
        r = self.client.get(self.url)
        self.assertContains(r, "As datas desta mostra são divulgadas aqui")

    def test_a_ultima_etapa_e_a_que_fica_em_destaque(self):
        Etapa.objects.create(submissao=self.cientifica, titulo="Resultado", inicio=date(2026, 10, 22))
        Etapa.objects.create(
            submissao=self.cientifica, titulo="Envio",
            inicio=date(2026, 9, 24), fim=date(2026, 10, 12),
        )

        html = self.client.get(self.url).content.decode()
        self.assertLess(html.index("Envio</h4>"), html.index("Resultado</h4>"))
        destaque = html.index("etapa--fecho")
        self.assertLess(html.index("Envio</h4>"), destaque)
        self.assertLess(destaque, html.index("Resultado</h4>"))

    def test_aberta_mostra_o_botao_de_envio(self):
        self.abrir()
        r = self.client.get(self.url)
        self.assertContains(r, "https://forms.exemplo.invalid/trabalhos")
        self.assertContains(r, "Enviar meu trabalho")

    def test_os_documentos_vem_antes_do_botao_de_envio(self):
        self.abrir()
        Anexo.objects.create(
            submissao=self.cientifica, titulo="Regulamento", link="https://exemplo.invalid/reg.pdf"
        )

        html = self.client.get(self.url).content.decode()
        self.assertLess(html.index("Regulamento</h4>"), html.index('id="mostra-cientifica-envio"'))

    def test_documento_fora_do_ar_nao_aparece(self):
        Anexo.objects.create(
            submissao=self.cientifica,
            titulo="Edital antigo", link="https://exemplo.invalid/velho.pdf", publicado=False
        )
        Anexo.objects.create(submissao=self.cientifica, titulo="Regulamento", link="https://exemplo.invalid/reg.pdf")

        r = self.client.get(self.url)
        self.assertContains(r, "Regulamento")
        self.assertNotContains(r, "Edital antigo")

    def test_a_ordem_e_a_do_campo_ordem(self):
        Anexo.objects.create(submissao=self.cientifica, titulo="Segundo", link="https://exemplo.invalid/2", ordem=2)
        Anexo.objects.create(submissao=self.cientifica, titulo="Primeiro", link="https://exemplo.invalid/1", ordem=1)

        html = self.client.get(self.url).content.decode()
        self.assertLess(html.index("Primeiro"), html.index("Segundo"))

    def test_arquivo_enviado_e_servido_pelo_site(self):
        anexo = Anexo(submissao=self.cientifica, titulo="Regulamento")
        anexo.arquivo.save("regulamento.pdf", SimpleUploadedFile("regulamento.pdf", b"%PDF-1.4 "))

        r = self.client.get(self.url)
        self.assertContains(r, anexo.arquivo.url)
        self.assertContains(r, "PDF")
        # arquivo do próprio site baixa; só o de fora abre em outra aba
        self.assertContains(r, "Baixar")
        self.assertContains(r, "download")
        self.assertNotContains(r, "Abrir")

    def test_documento_de_fora_abre_em_outra_aba(self):
        Anexo.objects.create(submissao=self.cientifica, titulo="Pasta no Drive", link="https://drive.exemplo.invalid/pasta")

        r = self.client.get(self.url)
        self.assertContains(r, "https://drive.exemplo.invalid/pasta")
        self.assertContains(r, "Abrir")

    def test_o_texto_do_documento_sai_escapado(self):
        Anexo.objects.create(
            submissao=self.cientifica,
            titulo="Regulamento",
            descricao="<script>alert(1)</script>",
            link="https://exemplo.invalid/reg.pdf",
        )
        r = self.client.get(self.url)
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")

    def test_a_home_so_oferece_o_regulamento_quando_ha_documento(self):
        # fechada e sem documento: nada a visitar, só o aviso
        self.assertNotContains(self.client.get(reverse("home")), "Ver o regulamento")

        Anexo.objects.create(submissao=self.cientifica, titulo="Regulamento", link="https://exemplo.invalid/reg.pdf")
        self.assertContains(self.client.get(reverse("home")), "Ver o regulamento")


@override_settings(MEDIA_ROOT=MIDIA_DE_TESTE)
class AnexosPeloPainel(Base):
    """Os documentos são da organização: só o administrador mexe."""

    url = reverse_lazy("painel:anexos")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MIDIA_DE_TESTE, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        Anexo.objects.all().delete()

    def dados(self, **mudancas):
        base = {
            "submissao": str(self.cientifica.pk),
            "titulo": "Regulamento",
            "descricao": "As regras da submissão.",
            "link": "https://exemplo.invalid/regulamento.pdf",
            "ordem": "0",
            "publicado": "on",
        }
        base.update(mudancas)
        return base

    def test_administrador_publica_um_documento(self):
        self.entrar("admin")
        r = self.client.post(reverse("painel:anexo_novo"), self.dados())
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Anexo.objects.get().titulo, "Regulamento")

    def test_administrador_envia_um_arquivo(self):
        self.entrar("admin")
        arquivo = SimpleUploadedFile("modelo.docx", b"PK\x03\x04 conteudo")
        r = self.client.post(
            reverse("painel:anexo_novo"),
            self.dados(titulo="Modelo", link="", arquivo=arquivo),
        )
        self.assertEqual(r.status_code, 302)

        anexo = Anexo.objects.get()
        self.assertTrue(anexo.arquivo.name.endswith(".docx"))
        self.assertEqual(anexo.formato, "DOCX")
        self.assertFalse(anexo.externo)

    def test_arquivo_e_link_juntos_sao_recusados(self):
        self.entrar("admin")
        r = self.client.post(
            reverse("painel:anexo_novo"),
            self.dados(arquivo=SimpleUploadedFile("reg.pdf", b"%PDF-1.4 ")),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Anexo.objects.count(), 0)

    def test_sem_arquivo_e_sem_link_fica_como_em_breve(self):
        # documento anunciado e ainda não pronto: entra, mas sem botão
        self.entrar("admin")
        r = self.client.post(reverse("painel:anexo_novo"), self.dados(link=""))
        self.assertEqual(r.status_code, 302)

        anexo = Anexo.objects.get()
        self.assertFalse(anexo.disponivel)
        self.assertEqual(anexo.formato, "em breve")
        self.assertEqual(anexo.url, "")

        self.client.logout()
        pagina = self.client.get(reverse("trabalhos"))
        self.assertContains(pagina, "Regulamento")
        self.assertContains(pagina, "Ainda não publicado")
        self.assertNotContains(pagina, 'href=""')

    def test_o_slug_sai_do_titulo(self):
        self.entrar("admin")
        self.client.post(reverse("painel:anexo_novo"), self.dados(titulo="Regulamento da SNCT"))
        self.assertEqual(Anexo.objects.get().slug, "regulamento-da-snct")

    @override_settings(TAMANHO_MAXIMO_ANEXO=1024)
    def test_arquivo_grande_demais_e_recusado(self):
        # O limite é de verdade 30 MB; aqui ele é apertado para o teste não
        # precisar carregar 30 MB na memória só para ver a recusa acontecer.
        self.entrar("admin")
        grande = SimpleUploadedFile("enorme.pdf", b"x" * 2048)
        r = self.client.post(
            reverse("painel:anexo_novo"), self.dados(link="", arquivo=grande)
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Anexo.objects.count(), 0)

    def test_o_limite_de_envio_e_de_30_mb(self):
        # Um regulamento digitalizado passa dos 10 MB com facilidade.
        self.assertEqual(settings.TAMANHO_MAXIMO_ANEXO, 30 * 1024 * 1024)

    def test_excluir_apaga_o_arquivo_do_disco(self):
        self.entrar("admin")
        anexo = Anexo(submissao=self.cientifica, titulo="Modelo")
        anexo.arquivo.save("modelo.docx", SimpleUploadedFile("modelo.docx", b"conteudo"))
        caminho = anexo.arquivo.path

        self.client.post(reverse("painel:anexo_excluir", args=[anexo.pk]))
        self.assertEqual(Anexo.objects.count(), 0)
        self.assertFalse(pathlib.Path(caminho).exists())

    def test_coordenacao_nao_abre_a_lista(self):
        self.entrar("coord_ads")
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_coordenacao_nao_publica_por_post_direto(self):
        self.entrar("coord_ads")
        r = self.client.post(reverse("painel:anexo_novo"), self.dados())
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Anexo.objects.count(), 0)

    def test_coordenacao_nao_exclui_por_post_direto(self):
        anexo = Anexo.objects.create(submissao=self.cientifica, titulo="Regulamento", link="https://exemplo.invalid/r.pdf")
        self.entrar("coord_ads")
        r = self.client.post(reverse("painel:anexo_excluir", args=[anexo.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Anexo.objects.count(), 1)

    def test_visitante_nao_chega_nem_na_lista(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("painel:entrar"), r["Location"])

    def test_get_nao_exclui(self):
        anexo = Anexo.objects.create(submissao=self.cientifica, titulo="Regulamento", link="https://exemplo.invalid/r.pdf")
        self.entrar("admin")
        r = self.client.get(reverse("painel:anexo_excluir", args=[anexo.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Anexo.objects.count(), 1)

    def test_documento_precisa_de_mostra(self):
        self.entrar("admin")
        r = self.client.post(reverse("painel:anexo_novo"), self.dados(submissao=""))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Anexo.objects.count(), 0)

    def test_o_mesmo_titulo_em_outra_mostra_ganha_outro_endereco(self):
        # cada mostra tem o seu "Regulamento"; /trabalhos/regulamento/ é o da
        # primeira, que é o endereço já divulgado
        self.entrar("admin")
        self.client.post(reverse("painel:anexo_novo"), self.dados())
        r = self.client.post(
            reverse("painel:anexo_novo"), self.dados(submissao=str(self.empreendedora.pk))
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(
            sorted(Anexo.objects.values_list("slug", flat=True)),
            ["regulamento", "regulamento-mostra-empreendedora-e-tecnologica"],
        )

    def test_adicionar_a_partir_da_mostra_ja_vem_com_ela_escolhida(self):
        self.entrar("admin")
        r = self.client.get(
            reverse("painel:anexo_novo") + f"?mostra={self.empreendedora.slug}"
        )
        self.assertEqual(r.context["form"].initial["submissao"], self.empreendedora)

    def test_a_lista_separa_por_mostra(self):
        Anexo.objects.create(
            submissao=self.empreendedora, titulo="Edital empreendedor",
            link="https://exemplo.invalid/e.pdf",
        )
        self.entrar("admin")
        html = self.client.get(self.url).content.decode()
        self.assertGreater(
            html.index("Edital empreendedor"),
            html.index('id="mostra-empreendedora-e-tecnologica"'),
        )

    def test_publicar_pelo_painel_muda_a_pagina_de_submissao(self):
        self.assertNotContains(
            self.client.get(reverse("trabalhos")), "https://exemplo.invalid/regulamento.pdf"
        )

        self.entrar("admin")
        self.client.post(reverse("painel:anexo_novo"), self.dados())

        self.client.logout()
        r = self.client.get(reverse("trabalhos"))
        self.assertContains(r, "Regulamento")
        self.assertContains(r, "https://exemplo.invalid/regulamento.pdf")


class InscricaoNoCronograma(Base):
    """Cada atividade pode ter inscrição própria; sem ela, vale a do curso."""

    url = reverse_lazy("cronograma")
    LINK_DA_AREA = "https://suap.ifro.edu.br/eventos/inscricao/1/111/"
    LINK_DO_EVENTO = "https://suap.ifro.edu.br/eventos/inscricao/1/222/"

    def abrir_a_area(self):
        self.ads.inscricoes_abertas = True
        self.ads.link_inscricao = self.LINK_DA_AREA
        self.ads.save()

    def test_sem_link_nenhum_nao_ha_botao(self):
        r = self.client.get(self.url)
        self.assertNotContains(r, "Inscreva-se")
        self.assertNotContains(r, 'href=""')

    def test_sem_link_proprio_usa_o_do_curso(self):
        self.abrir_a_area()
        r = self.client.get(self.url)
        self.assertContains(r, self.LINK_DA_AREA)
        self.assertContains(r, "Inscreva-se")
        self.assertNotContains(r, "inscrição só desta atividade")

    def test_link_proprio_tem_precedencia(self):
        self.abrir_a_area()
        self.ev_ads.link_inscricao = self.LINK_DO_EVENTO
        self.ev_ads.save()

        r = self.client.get(self.url)
        self.assertContains(r, self.LINK_DO_EVENTO)
        self.assertContains(r, "inscrição só desta atividade")
        self.assertEqual(self.ev_ads.url_inscricao, self.LINK_DO_EVENTO)

    def test_o_link_proprio_e_so_daquele_evento(self):
        self.abrir_a_area()
        self.ev_ads.link_inscricao = self.LINK_DO_EVENTO
        self.ev_ads.save()

        # o outro evento da mesma área continua no link do curso
        self.assertEqual(self.ev_ads.url_inscricao, self.LINK_DO_EVENTO)
        self.assertEqual(
            Evento.objects.get(pk=self.ev_ads.pk).area.link_inscricao, self.LINK_DA_AREA
        )
        outro = Evento.objects.create(titulo="Mesa-redonda", area=self.ads)
        Horario.objects.create(
            evento=outro, data=date(2026, 10, 30), hora_inicio=time(8, 0)
        )
        self.assertEqual(outro.url_inscricao, self.LINK_DA_AREA)

    def test_link_proprio_aparece_mesmo_com_o_curso_fechado(self):
        # o interruptor da área governa o link da área; um link colado na
        # atividade é decisão de quem cadastrou a atividade
        self.ev_ads.link_inscricao = self.LINK_DO_EVENTO
        self.ev_ads.save()

        r = self.client.get(self.url)
        self.assertContains(r, self.LINK_DO_EVENTO)
        self.assertTrue(self.ev_ads.mostra_botao_inscricao)

    def test_link_do_curso_fechado_nao_vaza(self):
        self.ads.link_inscricao = self.LINK_DA_AREA
        self.ads.save()  # sem inscricoes_abertas

        r = self.client.get(self.url)
        self.assertNotContains(r, self.LINK_DA_AREA)
        self.assertNotContains(r, "Inscreva-se")

    def test_a_coordenacao_cadastra_o_link_pelo_painel(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:editar", args=[self.ev_ads.pk]),
            self.dados(
                titulo=self.ev_ads.titulo,
                area=self.ads.pk,
                link_inscricao="suap.ifro.edu.br/eventos/inscricao/1/222/",
            ),
        )
        self.assertEqual(r.status_code, 302)
        # sem esquema no que foi colado, vira https
        self.assertEqual(
            Evento.objects.get(pk=self.ev_ads.pk).link_inscricao, self.LINK_DO_EVENTO
        )

    def test_link_invalido_e_recusado(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:editar", args=[self.ev_ads.pk]),
            self.dados(
                titulo=self.ev_ads.titulo, area=self.ads.pk, link_inscricao="não é link"
            ),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Evento.objects.get(pk=self.ev_ads.pk).link_inscricao, "")


class DocumentoNoSite(Base):
    """O regulamento não muda: além do arquivo, ele é lido no próprio site."""

    def setUp(self):
        Anexo.objects.all().delete()
        self.anexo = Anexo.objects.create(
            submissao=self.cientifica,
            titulo="Regulamento",
            texto="## Das regras\n\nO trabalho do Campus deve ser enviado\nem PDF.\n\n- até 10 páginas\n- em PDF",
        )

    def test_a_pagina_do_documento_abre(self):
        r = self.client.get(reverse("documento", args=["regulamento"]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Das regras")

    def test_a_marcacao_simples_vira_html(self):
        html = self.client.get(self.anexo.url_pagina).content.decode()
        self.assertIn("<h2>Das regras</h2>", html)
        self.assertIn("<li>até 10 páginas</li>", html)
        # linhas seguidas são um parágrafo só, e Campus sai em itálico
        self.assertIn("<p>O trabalho do <i>Campus</i> deve ser enviado em PDF.</p>", html)

    def test_negrito_com_dois_asteriscos(self):
        self.anexo.texto = "Apresentação na **modalidade banner**."
        self.anexo.save()
        html = self.client.get(self.anexo.url_pagina).content.decode()
        self.assertIn("<b>modalidade banner</b>", html)

    def test_a_volta_leva_a_mostra_do_documento(self):
        r = self.client.get(self.anexo.url_pagina)
        self.assertContains(r, f'href="{reverse("trabalhos")}#mostra-cientifica"')
        self.assertContains(r, f'href="{reverse("trabalhos")}#mostra-cientifica-envio"')
        self.assertContains(r, "Mostra Científica")

    def test_html_digitado_no_painel_nao_vira_marcacao(self):
        self.anexo.texto = "<script>alert(1)</script>"
        self.anexo.save()

        r = self.client.get(self.anexo.url_pagina)
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")

    def test_documento_sem_texto_nao_tem_pagina(self):
        self.anexo.texto = ""
        self.anexo.link = "https://exemplo.invalid/reg.pdf"
        self.anexo.save()
        self.assertEqual(self.client.get("/trabalhos/regulamento/").status_code, 404)

    def test_documento_fora_do_ar_nao_tem_pagina(self):
        self.anexo.publicado = False
        self.anexo.save()
        self.assertEqual(self.client.get(self.anexo.url_pagina).status_code, 404)

    def test_a_lista_oferece_ler_no_site(self):
        r = self.client.get(reverse("trabalhos"))
        self.assertContains(r, "Ler no site")
        self.assertContains(r, self.anexo.url_pagina)

    def test_texto_sem_arquivo_ainda_conta_como_conteudo(self):
        # o regulamento em texto já vale a visita, mesmo sem o PDF
        self.assertContains(self.client.get(reverse("home")), "Ver o regulamento")


class DocumentosSemeados(TestCase):
    """Os três documentos que a migração 0009 anuncia."""

    def test_os_tres_existem_na_ordem_certa(self):
        titulos = list(Anexo.objects.values_list("titulo", flat=True))
        self.assertEqual(
            titulos,
            ["Regulamento", "Template de Trabalho Completo", "Template de Resumo Simples"],
        )

    def test_entram_anunciados_e_sem_arquivo(self):
        for anexo in Anexo.objects.all():
            self.assertFalse(anexo.disponivel, anexo.titulo)
            self.assertTrue(anexo.publicado, anexo.titulo)
            self.assertEqual(anexo.formato, "em breve")

    def test_a_pagina_de_submissao_ja_os_anuncia(self):
        r = self.client.get(reverse("trabalhos"))
        self.assertContains(r, "Template de Trabalho Completo")
        self.assertContains(r, "Template de Resumo Simples")
        self.assertNotContains(r, 'href=""')

    def test_a_home_nao_promete_documento_que_ainda_nao_existe(self):
        self.assertNotContains(self.client.get(reverse("home")), "Ver o regulamento")


class MostrasSemeadas(TestCase):
    """O que as migrações 0012 a 0014 deixam no banco."""

    def test_sao_duas_na_ordem_certa(self):
        self.assertEqual(
            list(Submissao.objects.values_list("nome", flat=True)),
            ["Mostra Científica", "Mostra Empreendedora e Tecnológica"],
        )

    def test_os_documentos_que_existiam_sao_da_cientifica(self):
        cientifica = Submissao.objects.get(slug="mostra-cientifica")
        self.assertEqual(Anexo.objects.exclude(submissao=cientifica).count(), 0)
        self.assertEqual(cientifica.anexos.count(), 3)

    def test_a_cientifica_leva_as_quatro_datas_do_edital(self):
        cientifica = Submissao.objects.get(slug="mostra-cientifica")
        self.assertEqual(
            [(e.titulo, e.inicio, e.fim) for e in cientifica.etapas.all()],
            [
                ("Submissão", date(2026, 9, 24), date(2026, 10, 12)),
                ("Avaliação", date(2026, 9, 24), date(2026, 10, 15)),
                ("Correções", date(2026, 10, 16), date(2026, 10, 20)),
                ("Resultado final", date(2026, 10, 22), None),
            ],
        )

    def test_a_cientifica_leva_o_texto_da_chamada(self):
        cientifica = Submissao.objects.get(slug="mostra-cientifica")
        self.assertIn("**modalidade banner**", cientifica.resumo)

    def test_a_empreendedora_nasce_fechada_e_vazia(self):
        e = Submissao.objects.get(slug="mostra-empreendedora-e-tecnologica")
        self.assertFalse(e.aberta)
        self.assertFalse(e.links.exists())
        self.assertFalse(e.etapas.exists())
        self.assertFalse(e.anexos.exists())


class Saude(Base):
    def test_responde_ok(self):
        r = self.client.get(reverse("saude"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"ok\n")


class Acesso(Base):
    def test_painel_exige_login(self):
        r = self.client.get(reverse("painel:lista"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("painel:entrar"), r.url)

    def test_todas_as_paginas_do_painel_exigem_login(self):
        urls = [
            reverse("painel:lista"),
            reverse("painel:novo"),
            reverse("painel:inscricao", args=[self.ads.slug]),
            reverse("painel:submissao", args=["mostra-cientifica"]),
            reverse("painel:cartoes"),
            reverse("painel:cartao_novo"),
            reverse("painel:editar", args=[self.ev_ads.pk]),
            reverse("painel:excluir", args=[self.ev_ads.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_usuario_inativo_nao_entra(self):
        ok = self.client.login(username="inativo", password="senha-de-teste-123")
        self.assertFalse(ok)
        self.assertEqual(self.client.get(reverse("painel:lista")).status_code, 302)

    def test_coordenacao_nao_entra_no_django_admin(self):
        self.entrar("coord_ads")
        r = self.client.get("/admin/", follow=True)
        # o admin manda para a tela de login dele em vez de abrir
        self.assertNotContains(r, "Administração do site", status_code=200)

    def test_conta_sem_area_ve_explicacao_em_vez_de_formulario(self):
        self.entrar("sem_area")
        r = self.client.get(reverse("painel:lista"))
        self.assertContains(r, "ainda não tem curso/área")
        r = self.client.get(reverse("painel:novo"))
        self.assertContains(r, "ainda não tem curso/área")


class PermissoesDaCoordenacao(Base):
    def test_ve_somente_os_proprios_eventos(self):
        self.entrar("coord_ads")
        r = self.client.get(reverse("painel:lista"))
        self.assertContains(r, "Palestra sobre Inteligência Artificial")
        self.assertNotContains(r, "Workshop de Flutter")

    def test_cria_evento_na_propria_area(self):
        self.entrar("coord_ads")
        r = self.client.post(reverse("painel:novo"), self.dados(area=self.ads.pk))
        self.assertRedirects(r, reverse("painel:lista"))
        self.assertTrue(Evento.objects.filter(titulo="Evento de teste", area=self.ads).exists())

    def test_evento_criado_guarda_quem_criou(self):
        self.entrar("coord_ads")
        self.client.post(reverse("painel:novo"), self.dados(area=self.ads.pk))
        evento = Evento.objects.get(titulo="Evento de teste")
        self.assertEqual(evento.criado_por, self.coord_ads)

    def test_edita_evento_da_propria_area(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:editar", args=[self.ev_ads.pk]),
            self.dados(titulo="Título novo", area=self.ads.pk),
        )
        self.assertRedirects(r, reverse("painel:lista"))
        self.ev_ads.refresh_from_db()
        self.assertEqual(self.ev_ads.titulo, "Título novo")

    def test_exclui_evento_da_propria_area(self):
        self.entrar("coord_ads")
        r = self.client.post(reverse("painel:excluir", args=[self.ev_ads.pk]))
        self.assertRedirects(r, reverse("painel:lista"))
        self.assertFalse(Evento.objects.filter(pk=self.ev_ads.pk).exists())

    # ---------------------------------------------------------- o que não pode

    def test_nao_cria_evento_em_area_alheia(self):
        self.entrar("coord_ads")
        r = self.client.post(reverse("painel:novo"), self.dados(area=self.info.pk))
        self.assertEqual(r.status_code, 200)  # volta com erro, não redireciona
        self.assertFalse(Evento.objects.filter(titulo="Evento de teste").exists())

    def test_nao_abre_edicao_de_evento_alheio(self):
        self.entrar("coord_ads")
        r = self.client.get(reverse("painel:editar", args=[self.ev_info.pk]))
        self.assertEqual(r.status_code, 404)

    def test_nao_edita_evento_alheio_por_post_direto(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:editar", args=[self.ev_info.pk]),
            self.dados(titulo="Invadido", area=self.ads.pk),
        )
        self.assertEqual(r.status_code, 404)
        self.ev_info.refresh_from_db()
        self.assertEqual(self.ev_info.titulo, "Workshop de Flutter")

    def test_nao_exclui_evento_alheio_por_post_direto(self):
        self.entrar("coord_ads")
        r = self.client.post(reverse("painel:excluir", args=[self.ev_info.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Evento.objects.filter(pk=self.ev_info.pk).exists())

    def test_nao_move_evento_proprio_para_area_alheia(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:editar", args=[self.ev_ads.pk]),
            self.dados(titulo=self.ev_ads.titulo, area=self.info.pk),
        )
        self.assertEqual(r.status_code, 200)
        self.ev_ads.refresh_from_db()
        self.assertEqual(self.ev_ads.area, self.ads)

    def test_get_nao_exclui(self):
        self.entrar("coord_ads")
        r = self.client.get(reverse("painel:excluir", args=[self.ev_ads.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Excluir evento?")
        self.assertTrue(Evento.objects.filter(pk=self.ev_ads.pk).exists())


class DuasAreas(Base):
    def test_ve_as_duas_areas_e_nao_a_terceira(self):
        self.entrar("coord_duas")
        r = self.client.get(reverse("painel:lista"))
        self.assertContains(r, "Workshop de Flutter")
        self.assertNotContains(r, "Palestra sobre Inteligência Artificial")

    def test_pode_escolher_entre_as_duas_no_formulario(self):
        self.entrar("coord_duas")
        r = self.client.get(reverse("painel:novo"))
        opcoes = r.context["form"].fields["area"].queryset
        self.assertCountEqual(list(opcoes), [self.info, self.eletro])

    def test_uma_area_dispensa_a_escolha(self):
        self.entrar("coord_ads")
        r = self.client.get(reverse("painel:novo"))
        self.assertEqual(r.context["form"].area_unica, self.ads)


class Administrador(Base):
    def test_ve_eventos_de_todas_as_areas(self):
        self.entrar("admin")
        r = self.client.get(reverse("painel:lista"))
        self.assertContains(r, "Palestra sobre Inteligência Artificial")
        self.assertContains(r, "Workshop de Flutter")

    def test_edita_qualquer_evento(self):
        self.entrar("admin")
        r = self.client.post(
            reverse("painel:editar", args=[self.ev_info.pk]),
            self.dados(titulo="Editado pelo admin", area=self.info.pk),
        )
        self.assertRedirects(r, reverse("painel:lista"))
        self.ev_info.refresh_from_db()
        self.assertEqual(self.ev_info.titulo, "Editado pelo admin")

    def test_exclui_qualquer_evento(self):
        self.entrar("admin")
        self.client.post(reverse("painel:excluir", args=[self.ev_info.pk]))
        self.assertFalse(Evento.objects.filter(pk=self.ev_info.pk).exists())

    def test_cria_evento_em_qualquer_area(self):
        self.entrar("admin")
        r = self.client.post(reverse("painel:novo"), self.dados(area=self.eletro.pk))
        self.assertRedirects(r, reverse("painel:lista"))
        self.assertTrue(Evento.objects.filter(area=self.eletro).exists())

    def test_entra_no_django_admin(self):
        self.entrar("admin")
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_gerencia_usuarios_e_areas_pelo_admin(self):
        self.entrar("admin")
        for url in ["/admin/auth/user/", "/admin/eventos/area/", "/admin/eventos/evento/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_define_areas_de_um_usuario_pelo_admin(self):
        self.entrar("admin")
        r = self.client.post(
            f"/admin/auth/user/{self.coord_ads.pk}/change/",
            {
                "username": "coord_ads",
                "first_name": "",
                "last_name": "",
                "email": "",
                "is_active": "on",
                "areas": [self.ads.pk, self.info.pk],
                "last_login_0": "",
                "last_login_1": "",
                "date_joined_0": "2026-01-01",
                "date_joined_1": "00:00:00",
            },
        )
        self.assertEqual(r.status_code, 302, "o admin deveria salvar e redirecionar")
        self.assertCountEqual(
            list(self.coord_ads.areas_geridas.all()), [self.ads, self.info]
        )


class RegrasDoEvento(Base):
    def test_termino_antes_do_inicio_e_recusado(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:novo"),
            self.dados(
                area=self.ads.pk,
                **{"horarios-0-hora_inicio": "16:00", "horarios-0-hora_fim": "14:00"},
            ),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "depois do de início")
        self.assertFalse(Evento.objects.filter(titulo="Evento de teste").exists())

    def test_termino_e_opcional(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:novo"),
            self.dados(area=self.ads.pk, **{"horarios-0-hora_fim": ""}),
        )
        self.assertRedirects(r, reverse("painel:lista"))
        evento = Evento.objects.get(titulo="Evento de teste")
        self.assertIsNone(evento.horarios.get().hora_fim)

    def test_horario_formatado(self):
        horario = Horario(hora_inicio=time(14, 0), hora_fim=time(16, 30))
        self.assertEqual(horario.intervalo, "14:00 às 16:30")
        horario.hora_fim = None
        self.assertEqual(horario.intervalo, "14:00")

    def test_slug_sai_do_nome(self):
        area = Area.objects.create(nome="Medicina Veterinária")
        self.assertEqual(area.slug, "medicina-veterinaria")

    def test_area_com_evento_nao_e_apagada_por_acidente(self):
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.ads.delete()


class EventoComVariosHorarios(Base):
    """A regra pedida: repetição no mesmo dia é um cartão; em dias diferentes,
    um cartão por dia.

    É o que a mudança inteira existe para fazer, então é o que estes testes
    olham — pelo HTML que a pessoa vê, e não pelo agrupador por dentro.
    """

    def test_duas_sessoes_no_mesmo_dia_sao_um_cartao_so(self):
        evento = Evento.objects.create(titulo="Oficina de Robótica", area=self.ads)
        Horario.objects.create(
            evento=evento,
            data=date(2026, 10, 27),
            hora_inicio=time(9, 0),
            hora_fim=time(11, 0),
        )
        Horario.objects.create(
            evento=evento,
            data=date(2026, 10, 27),
            hora_inicio=time(14, 0),
            hora_fim=time(16, 0),
        )

        r = self.client.get(reverse("cronograma"))
        corpo = r.content.decode()

        # um cartão, com os dois horários dentro
        self.assertEqual(corpo.count("Oficina de Robótica"), 1)
        self.assertIn("09:00 às 11:00", corpo)
        self.assertIn("14:00 às 16:00", corpo)

    def test_dois_dias_diferentes_dao_um_cartao_em_cada(self):
        evento = Evento.objects.create(titulo="Mostra de Agronomia", area=self.ads)
        Horario.objects.create(
            evento=evento, data=date(2026, 10, 29), hora_inicio=time(8, 0)
        )
        Horario.objects.create(
            evento=evento, data=date(2026, 10, 30), hora_inicio=time(8, 0)
        )

        r = self.client.get(reverse("cronograma"))
        corpo = r.content.decode()
        self.assertEqual(corpo.count("Mostra de Agronomia"), 2)

    def test_o_total_conta_atividades_por_dia_e_nao_horarios(self):
        """Duas sessões num dia são uma linha do cronograma, e contam uma vez.

        Sem isto o rodapé diria "4 atividades" para quem vê três.
        """
        evento = Evento.objects.create(titulo="Oficina de Robótica", area=self.ads)
        Horario.objects.create(
            evento=evento, data=date(2026, 10, 27), hora_inicio=time(9, 0)
        )
        Horario.objects.create(
            evento=evento, data=date(2026, 10, 27), hora_inicio=time(14, 0)
        )

        r = self.client.get(reverse("cronograma"))
        # os dois da fixture, mais este, que ocupa uma linha só
        self.assertContains(r, "3 atividades")

    def test_painel_cadastra_evento_com_dois_horarios(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:novo"),
            self.dados(
                area=self.ads.pk,
                **{
                    "horarios-TOTAL_FORMS": "2",
                    "horarios-1-data": "2026-10-31",
                    "horarios-1-hora_inicio": "10:00",
                    "horarios-1-hora_fim": "",
                },
            ),
        )
        self.assertRedirects(r, reverse("painel:lista"))
        evento = Evento.objects.get(titulo="Evento de teste")
        self.assertEqual(evento.horarios.count(), 2)

    def test_evento_sem_nenhum_horario_e_recusado(self):
        """Evento sem horário não aparece em lugar nenhum do site — o
        cronograma percorre Horario. Então o formulário não deixa criar um."""
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:novo"),
            self.dados(
                area=self.ads.pk,
                **{
                    "horarios-TOTAL_FORMS": "1",
                    "horarios-0-data": "",
                    "horarios-0-hora_inicio": "",
                },
            ),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "pelo menos um dia e horário")
        self.assertFalse(Evento.objects.filter(titulo="Evento de teste").exists())

    def test_dois_horarios_iguais_sao_recusados(self):
        self.entrar("coord_ads")
        r = self.client.post(
            reverse("painel:novo"),
            self.dados(
                area=self.ads.pk,
                **{
                    "horarios-TOTAL_FORMS": "2",
                    "horarios-1-data": "2026-10-30",
                    "horarios-1-hora_inicio": "09:00",
                    "horarios-1-hora_fim": "",
                },
            ),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "dois horários iguais")
        self.assertFalse(Evento.objects.filter(titulo="Evento de teste").exists())

    def test_excluir_evento_leva_os_horarios_junto(self):
        evento = Evento.objects.create(titulo="Some tudo", area=self.ads)
        Horario.objects.create(
            evento=evento, data=date(2026, 10, 27), hora_inicio=time(9, 0)
        )
        self.entrar("coord_ads")
        self.client.post(reverse("painel:excluir", args=[evento.pk]))
        self.assertFalse(Horario.objects.filter(evento_id=evento.pk).exists())
