"""Testes do que não pode dar errado: quem pode mexer em quê.

Todo teste de permissão aqui bate direto na URL, com POST de verdade. Esconder
o botão na tela não conta — o que conta é o servidor recusar.
"""

from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Area, Evento


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        # A migração 0002 semeia as áreas reais da semana. Os testes montam o
        # próprio cenário, então começam do zero para não depender dela.
        Area.objects.all().delete()

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
            data=date(2026, 10, 28),
            hora_inicio=time(14, 0),
            local="Auditório",
            area=cls.ads,
        )
        cls.ev_info = Evento.objects.create(
            titulo="Workshop de Flutter",
            data=date(2026, 10, 29),
            hora_inicio=time(16, 0),
            local="Laboratório 03",
            area=cls.info,
        )

    def entrar(self, usuario):
        ok = self.client.login(username=usuario, password="senha-de-teste-123")
        self.assertTrue(ok, f"{usuario} deveria conseguir entrar")

    def dados(self, **troca):
        base = {
            "titulo": "Evento de teste",
            "data": "2026-10-30",
            "hora_inicio": "09:00",
            "hora_fim": "",
            "local": "Sala 1",
            "descricao": "",
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
        r = self.client.get(reverse("home"))
        for slug in ["cieec", "geral", "agronomia-e-agropecuaria", "alimentos",
                     "informatica", "biologia", "medicina-veterinaria"]:
            with self.subTest(slug=slug):
                self.assertContains(r, f'href="/cronograma/?area={slug}"')

    def test_area_desativada_nao_aparece_no_publico(self):
        self.ads.ativo = False
        self.ads.save()
        r = self.client.get(reverse("cronograma"))
        self.assertNotContains(r, "Palestra sobre Inteligência Artificial")

    def test_alteracao_no_painel_aparece_no_cronograma(self):
        self.entrar("coord_ads")
        self.client.post(
            reverse("painel:editar", args=[self.ev_ads.pk]),
            self.dados(titulo=self.ev_ads.titulo, hora_inicio="15:00", area=self.ads.pk),
        )
        self.client.logout()

        r = self.client.get(reverse("cronograma"))
        self.assertContains(r, "15:00")
        self.assertNotContains(r, "14:00")


class InscricaoNaHome(Base):
    """A inscrição é dado, não HTML: a organização abre e fecha pelo /admin/."""

    def setUp(self):
        # os cartões da home apontam para os slugs reais da semana
        self.cieec = Area.objects.create(nome="CIEEC", slug="cieec")

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
            self.dados(area=self.ads.pk, hora_inicio="16:00", hora_fim="14:00"),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "depois do de início")
        self.assertFalse(Evento.objects.filter(titulo="Evento de teste").exists())

    def test_termino_e_opcional(self):
        self.entrar("coord_ads")
        r = self.client.post(reverse("painel:novo"), self.dados(area=self.ads.pk, hora_fim=""))
        self.assertRedirects(r, reverse("painel:lista"))
        self.assertIsNone(Evento.objects.get(titulo="Evento de teste").hora_fim)

    def test_horario_formatado(self):
        evento = Evento(hora_inicio=time(14, 0), hora_fim=time(16, 30))
        self.assertEqual(evento.horario, "14:00 às 16:30")
        evento.hora_fim = None
        self.assertEqual(evento.horario, "14:00")

    def test_slug_sai_do_nome(self):
        area = Area.objects.create(nome="Medicina Veterinária")
        self.assertEqual(area.slug, "medicina-veterinaria")

    def test_area_com_evento_nao_e_apagada_por_acidente(self):
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.ads.delete()
