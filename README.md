# 23ª SNCT — IFRO Campus Ariquemes

Página da 23ª Semana Nacional de Ciência e Tecnologia do IFRO Campus Ariquemes.
Site estático, publicado pelo GitHub Pages em **snctifroari.online**.

Não tem build, nem dependência, nem passo de instalação: o que está no repositório
é o que vai para o ar. Basta editar e dar `git push`.

## Arquivos

```
index.html                 a página inteira
CNAME                      o domínio próprio (não mexer)
.nojekyll                  desliga o Jekyll no GitHub Pages
assets/css/style.css       todo o estilo
assets/js/site.js          contagem de dias, realce do menu, sombra do topo
assets/img/                marca do IFRO em SVG, favicon e imagem de compartilhamento
assets/marca-ifro/         PNGs e PDF originais da marca (origem dos SVGs)
.impeccable.md             as decisões de design, e por quê
```

## Ver a página no computador antes de publicar

Abrir o `index.html` direto no navegador funciona, mas dá para servir a pasta
como o GitHub Pages serve:

```bash
python3 -m http.server 8000
# depois abra http://localhost:8000
```

## O que ainda falta preencher

Está tudo marcado no HTML como `a confirmar` — dá para achar com
`grep -n "a confirmar" index.html`:

- **nome dos responsáveis** de 6 dos 7 eventos (só o IFROmatizando está definido);
- **contato** da comissão organizadora, na ficha da seção "Sobre";
- **links de inscrição** do SUAP dos eventos que ainda não abriram.

### Como marcar um evento com inscrição aberta

O bloco do **IFROmatizando**, dentro de `index.html`, já está no formato final e
serve de modelo. São três mudanças no `<article>` do evento:

1. acrescentar o atributo `data-aberto` na tag `<article>`;
2. acrescentar `<span class="selo-aberto">Inscrições abertas</span>` dentro do
   `<p class="evento__topo">`;
3. trocar o `<span class="em-breve">Inscrições em breve</span>` pelo botão com o
   link do SUAP.

Há um comentário com esse passo a passo logo acima da lista de eventos, no
próprio HTML.

## A marca do IFRO

Os arquivos em `assets/img/ifro-*.svg` foram extraídos do PDF vetorial oficial do
campus (`assets/marca-ifro/Logotipo IFRO - Ariquemes.pdf`), então são a marca de
verdade, e não um desenho aproximado — ficam nítidos em qualquer tamanho.
O símbolo isolado (`if-mark.svg`) foi reconstruído com a geometria medida nesse
mesmo arquivo: grade 3×4, célula 100, vão 20, canto com 9,7% do lado.

Cores oficiais: verde `#39A048`, vermelho `#CD2027`.

Cada logo tem a versão colorida e a versão branca (sufixo `-branca`), para fundo
claro e fundo escuro.
