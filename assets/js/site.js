/* 23ª SNCT — IFRO Campus Ariquemes
 *
 * Tudo aqui é enfeite: a página inteira é HTML servido de uma vez e a
 * revelação no scroll é CSS. Se este arquivo não carregar, nada de
 * conteúdo desaparece — só a contagem, o realce do menu e a sombra do
 * topo deixam de existir.
 */
(function () {
  "use strict";

  var topo = document.querySelector(".topo");

  /* ----------------------------------------------------------------------
   * 1. Altura real do topo fixo
   * O CSS usa --altura-topo no scroll-padding para o link de âncora não
   * parar atrás da barra. No celular a barra tem duas linhas, então o
   * valor precisa ser medido, não chutado.
   * -------------------------------------------------------------------- */
  function mediraTopo() {
    if (!topo) return;
    document.documentElement.style.setProperty(
      "--altura-topo",
      topo.getBoundingClientRect().height + "px"
    );
  }

  mediraTopo();
  if (topo && "ResizeObserver" in window) {
    new ResizeObserver(mediraTopo).observe(topo);
  } else {
    window.addEventListener("resize", mediraTopo, { passive: true });
  }

  /* ----------------------------------------------------------------------
   * 2. Sombra do topo apenas depois que a página rola
   * -------------------------------------------------------------------- */
  if (topo) {
    var sentinela = document.createElement("div");
    sentinela.setAttribute("aria-hidden", "true");
    sentinela.style.cssText = "position:absolute;top:0;left:0;width:1px;height:1px;";
    document.body.prepend(sentinela);

    new IntersectionObserver(function (entradas) {
      if (entradas[0].isIntersecting) topo.removeAttribute("data-rolado");
      else topo.setAttribute("data-rolado", "");
    }).observe(sentinela);
  }

  /* ----------------------------------------------------------------------
   * 3. Contagem para o início da semana
   * As datas vêm do HTML (data-inicio / data-fim), com fuso -04:00, para
   * que a página não precise ser editada em dois lugares.
   * -------------------------------------------------------------------- */
  var contagem = document.getElementById("contagem");

  if (contagem) {
    var inicio = new Date(contagem.dataset.inicio);
    var fim = new Date(contagem.dataset.fim);

    if (!isNaN(inicio) && !isNaN(fim)) {
      contagem.innerHTML = textoDaContagem(new Date(), inicio, fim);
      contagem.hidden = false;
    }
  }

  function textoDaContagem(agora, inicio, fim) {
    if (agora >= fim) return "Edição encerrada.<br>Até a próxima.";
    if (agora >= inicio) return "<b>Agora</b> acontecendo no campus";

    /* diferença em dias de calendário, não em blocos de 24 h: quem abre a
       página às 23 h da véspera tem que ler "amanhã", e não "0 dias". */
    var dias = Math.ceil((diaCheio(inicio) - diaCheio(agora)) / 86400000);

    if (dias <= 0) return "<b>É hoje</b>";
    if (dias === 1) return "<b>Amanhã</b> começa";
    return "<b>" + dias + "</b> dias para começar";
  }

  function diaCheio(d) {
    return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate());
  }

  /* ----------------------------------------------------------------------
   * 4. Seção corrente marcada no menu
   * -------------------------------------------------------------------- */
  var itens = Array.prototype.slice.call(
    document.querySelectorAll('.menu a[href^="#"]')
  );

  if (itens.length && "IntersectionObserver" in window) {
    var porId = {};
    var secoes = [];

    itens.forEach(function (a) {
      var alvo = document.getElementById(a.hash.slice(1));
      if (!alvo) return;
      porId[alvo.id] = a;
      secoes.push(alvo);
    });

    /* uma faixa estreita logo abaixo do topo decide qual seção está "em foco" */
    var vigia = new IntersectionObserver(
      function (entradas) {
        entradas.forEach(function (e) {
          if (!e.isIntersecting) return;
          itens.forEach(function (a) { a.removeAttribute("aria-current"); });
          porId[e.target.id].setAttribute("aria-current", "true");
        });
      },
      { rootMargin: "-30% 0px -65% 0px" }
    );

    secoes.forEach(function (s) { vigia.observe(s); });
  }
})();
