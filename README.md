# 23ª SNCT — IFRO Campus Ariquemes

Site da 23ª Semana Nacional de Ciência e Tecnologia do IFRO Campus Ariquemes,
com cronograma gerenciado pelas próprias coordenações.

Aplicação Django + PostgreSQL, em container, sob o domínio
**snctifroari.online**. Sobe com um `docker compose up -d`.

```
                    SNCT IFRO
                       │
              ┌────────┴────────┐
              │                 │
           Público          Coordenação
              │                 │
              ▼                 ▼
     /  e  /cronograma/      /painel/
              └────────┬────────┘
                       ▼
                     Django
                       ▼
                   PostgreSQL
```

## O que tem

| Endereço | Quem entra | Para quê |
|---|---|---|
| `/` | qualquer um | página da semana (a mesma de sempre) |
| `/cronograma/` | qualquer um | cronograma, dia por dia, vindo do banco |
| `/painel/` | coordenações | cadastrar os eventos das próprias áreas e abrir/fechar a inscrição delas |
| `/admin/` | só o administrador | contas, cursos/áreas e todos os eventos |

A permissão é por **curso/área**. Uma conta de coordenação pode cuidar de uma
ou de várias áreas, e só mexe nos eventos delas. A checagem é feita no
servidor: pedir pela URL o evento de outra área devolve 404, mesmo que o botão
não apareça na tela.

---

## Rodar na sua máquina

Precisa de Python 3.12 ou mais novo. A imagem de produção usa 3.13.

```bash
git clone https://github.com/PolarIF/SNCT2026.git
cd SNCT2026

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env               # e edite: gere uma SECRET_KEY, deixe DEBUG=1

python manage.py migrate
python manage.py createsuperuser   # essa é a sua conta de administrador
python manage.py runserver
```

Abra <http://127.0.0.1:8000/>.

Sem a variável `DATABASE_URL`, o projeto usa um arquivo SQLite (`db.sqlite3`) —
o suficiente para desenvolver. A migração inicial já cria os cursos/áreas que
apareciam na página: Geral, CIEEC, Agronomia e Agropecuária, Alimentos,
Informática, Biologia e Medicina Veterinária.

### Rodar os testes

```bash
python manage.py test
```

São 56 testes, a maioria sobre permissão: o que cada tipo de conta consegue e
não consegue fazer, inclusive por POST direto na URL. Também cobrem o estado
das inscrições na página inicial e o filtro do cronograma.

---

## Primeiros passos como administrador

Depois do `createsuperuser`, entre em `/admin/`.

### 1. Conferir os cursos/áreas

**Cursos/áreas** → a lista já vem preenchida. Renomeie, desative ou acrescente
o que faltar. Desativar esconde a área do site sem apagar os eventos dela.

### 2. Criar a conta de uma coordenação

**Usuários → Adicionar usuário**:

- **Usuário**: algo simples, tipo `coord_informatica`
- **Senha**: defina uma e passe para a coordenação
- **Cursos/áreas que esta conta pode administrar**: marque as áreas dela

Deixe **is_superuser** e **is_staff** desmarcados. Coordenação não usa o
`/admin/` — ela usa o `/painel/`.

### 3. Dar mais uma área para uma conta existente

Dois caminhos, tanto faz:

- **Usuários** → abra a conta → marque a área a mais; ou
- **Cursos/áreas** → abra a área → acrescente a pessoa em "quem pode administrar".

### 4. Abrir a inscrição de um curso/área

Isso **quem faz é a própria coordenação**, no painel — não precisa passar por
você. Em `/painel/`, no bloco "Inscrições", ela clica em *Alterar* na área
dela, marca **inscrições abertas** e cola o link do SUAP. O cartão daquele
curso na página inicial troca na hora o "Inscrições em breve" pelo botão
vermelho "Inscreva-se".

Você também alcança isso em **Cursos/áreas**, para qualquer área, e a coluna
"inscrições abertas" é editável direto na lista — dá para abrir ou fechar as
sete de uma vez.

Sem link, a caixa marcada só mostra o selo "Inscrições abertas" e nenhum
botão — de propósito, para não gerar link quebrado. O painel avisa isso com
"Falta o link".

### 5. Desativar uma conta

**Usuários** → abra a conta → desmarque **Ativo**. Ela deixa de conseguir
entrar, e os eventos que cadastrou continuam no lugar.

### 6. Trocar uma senha

**Usuários** → abra a conta → no campo de senha, clique no link para definir
uma nova.

---

## Colocar no ar

O site roda em container. Quem administra o servidor tem o passo a passo
completo em **[IMPLANTACAO.md](IMPLANTACAO.md)** — em resumo:

```bash
git clone https://github.com/PolarIF/SNCT2026.git
cd SNCT2026
cp .env.producao.exemplo .env    # preencher
docker compose up -d --build
```

Sobem três containers: a aplicação, o PostgreSQL e um proxy que resolve o
certificado HTTPS sozinho. As migrações rodam no início de cada container e a
primeira conta de administrador é criada a partir do `.env`, então não é
preciso rodar nada à mão no servidor depois.

Para atualizar: `git pull && docker compose up -d --build`.

## Estrutura

```
manage.py
requirements.txt
.env.example             modelo do .env de desenvolvimento

Dockerfile               a imagem da aplicação
docker-compose.yml       aplicação + PostgreSQL + proxy com HTTPS
Caddyfile                o proxy: certificado automático
scripts/entrypoint.sh    migra e garante o administrador a cada boot
.env.producao.exemplo    modelo do .env do servidor
IMPLANTACAO.md           passo a passo para quem administra o servidor

config/
  settings.py            tudo que varia entre máquinas vem de variável de ambiente
  urls.py

eventos/
  models.py              Area, Evento e a função areas_do_usuario()
  views.py               site público e painel
  forms.py               formulário de evento (limita as áreas do usuário)
  admin.py               Django Admin, incluindo o campo de áreas no usuário
  templatetags/snct.py   filtro que liga cada cartão da home à sua área
  management/commands/   criar_admin: a conta inicial, a partir do .env
  tests.py               56 testes, sobretudo de permissão
  migrations/
    0001_initial.py
    0002_areas_iniciais.py       cria os cursos/áreas da semana
    0003_inscricao_por_area.py   link e estado da inscrição
    0004_link_do_ifromatizando.py

templates/
  base.html              cabeçalho, rodapé e meta tags do site público
  index.html             a página da semana
  cronograma.html        o cronograma público
  painel/                as telas da coordenação

static/
  css/style.css          o site
  css/painel.css         o painel
  js/site.js             contagem de dias, realce do menu, sombra do topo
  img/                   marca do IFRO em SVG, favicon, imagem de compartilhamento

marca-ifro/              PNGs e PDF originais da marca (não são servidos)
.impeccable.md           as decisões de design da página pública
```

### Onde está a regra de permissão

Em um lugar só: `areas_do_usuario()`, em `eventos/models.py`. As views e o
formulário chamam essa função, então mudar a regra é mudar uma função.

- **Listar** — `Evento.objects.filter(area__in=areas_do_usuario(user))`
- **Criar/editar** — o campo de área do formulário só aceita essas áreas, e é a
  mesma queryset que valida o POST
- **Editar/excluir** — `get_object_or_404(..., area__in=areas_do_usuario(user))`
- **Inscrição** — `get_object_or_404(areas_do_usuario(user), slug=slug)`
- **Administrador** — `is_superuser` recebe todas as áreas ativas

---

## Sobre a página pública

A página inicial não foi redesenhada nesta etapa. Ela virou um template Django
(`templates/index.html`), com o cabeçalho e o rodapé movidos para
`base.html` para não ficarem duplicados no cronograma.

As duas únicas mudanças visíveis foram as necessárias para o cronograma existir:

- **Cronograma** entrou como um item a mais no menu do topo;
- a faixa "Como a semana se divide" ganhou o link *Ver o cronograma completo*.

O resto foi conferido comparando as capturas antes e depois: fora essas duas
regiões, o que muda são bordas de 1px que caem em outro pixel por
arredondamento de layout.

Ainda falta preencher, na página inicial (`grep -n "a confirmar" templates/index.html`):

- nome dos responsáveis de 6 dos 7 eventos;
- contato da comissão organizadora.

Os links de inscrição **não** ficam mais no HTML: são cadastrados em
/admin/ → Cursos/áreas, um por curso/área.

### A marca do IFRO

Os SVGs em `static/img/ifro-*.svg` foram extraídos do PDF vetorial oficial do
campus (`marca-ifro/Logotipo IFRO - Ariquemes.pdf`), então são a marca de
verdade. O símbolo isolado (`if-mark.svg`) foi reconstruído com a geometria
medida nesse mesmo arquivo: grade 3×4, célula 100, vão 20, canto com 9,7% do
lado.

Cores oficiais: verde `#39A048`, vermelho `#CD2027`.

---

## Segurança

O que está ligado quando `DEBUG=0`:

- senhas com o hasher do Django (PBKDF2) e os validadores padrão;
- sessão por cookie, com `Secure` e CSRF em todo formulário;
- HTTPS obrigatório, atrás do proxy do Railway (`X-Forwarded-Proto`);
- HSTS por 30 dias, `nosniff`, `X-Frame-Options: DENY`;
- `ALLOWED_HOSTS` fechado: requisição com outro `Host` recebe 400;
- autorização no servidor, e não em esconder botões;
- conta desativada não entra.

`manage.py check --deploy` passa com um aviso só, o de `SECURE_HSTS_PRELOAD`.
Está desligado de propósito: entrar na lista de preload dos navegadores é
difícil de desfazer, e não vale para um site de uma semana de evento.
