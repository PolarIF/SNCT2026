# 23ª SNCT — IFRO Campus Ariquemes

Site da 23ª Semana Nacional de Ciência e Tecnologia do IFRO Campus Ariquemes,
com cronograma gerenciado pelas próprias coordenações.

Aplicação Django + PostgreSQL, preparada para rodar no Railway sob o domínio
**snctifroari.online**.

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
| `/painel/` | coordenações | cadastrar, editar e excluir os eventos das próprias áreas |
| `/admin/` | só o administrador | contas, cursos/áreas e todos os eventos |

A permissão é por **curso/área**. Uma conta de coordenação pode cuidar de uma
ou de várias áreas, e só mexe nos eventos delas. A checagem é feita no
servidor: pedir pela URL o evento de outra área devolve 404, mesmo que o botão
não apareça na tela.

---

## Rodar na sua máquina

Precisa de Python 3.12 ou mais novo (aqui foi testado no 3.14).

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

São 36 testes, a maioria sobre permissão: o que cada tipo de conta consegue e
não consegue fazer, inclusive por POST direto na URL.

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

### 4. Desativar uma conta

**Usuários** → abra a conta → desmarque **Ativo**. Ela deixa de conseguir
entrar, e os eventos que cadastrou continuam no lugar.

### 5. Trocar uma senha

**Usuários** → abra a conta → no campo de senha, clique no link para definir
uma nova.

---

## Deploy no Railway

### 1. Criar o projeto

No Railway: **New Project → Deploy from GitHub repo** e escolha este
repositório. O Railway detecta Python pelo `requirements.txt` e usa o
`Procfile`, que roda as migrações antes de subir o servidor.

### 2. Ligar o PostgreSQL

No projeto: **New → Database → Add PostgreSQL**. Depois, no serviço da
aplicação, em **Variables**, crie `DATABASE_URL` com a referência do banco:

```
DATABASE_URL = ${{ Postgres.DATABASE_URL }}
```

### 3. Variáveis de ambiente

No serviço da aplicação, em **Variables**:

| Variável | Valor |
|---|---|
| `SECRET_KEY` | uma chave longa e aleatória (veja abaixo) |
| `DEBUG` | `0` |
| `ALLOWED_HOSTS` | `snctifroari.online,www.snctifroari.online` |
| `DATABASE_URL` | `${{ Postgres.DATABASE_URL }}` |

Para gerar a `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Nunca comite essa chave. Se ela vazar, gere outra e troque a variável — o
efeito é só derrubar as sessões abertas.

O domínio que o Railway gera (`*.up.railway.app`) entra sozinho na lista de
hosts permitidos, então dá para testar antes de mexer no DNS.

### 4. Criar o administrador em produção

Com a Railway CLI:

```bash
railway run python manage.py createsuperuser
```

Ou pelo terminal do serviço, no painel do Railway.

### 5. Ligar o domínio

No serviço: **Settings → Networking → Custom Domain**, adicione
`snctifroari.online`. O Railway mostra o registro DNS exato para criar no seu
provedor — use o valor que ele mostrar, não um decorado daqui.

Um detalhe de DNS: o Railway pede um **CNAME**, e a maioria dos provedores não
aceita CNAME no domínio raiz. Duas saídas:

- usar um provedor que faça achatamento de CNAME (ALIAS/ANAME) na raiz —
  o Cloudflare faz; ou
- apontar `www.snctifroari.online` para o Railway e configurar o redirecionamento
  da raiz para o `www` no provedor.

### 6. Só depois: desligar o GitHub Pages

O site era publicado pelo GitHub Pages a partir da branch `main`. Os arquivos
`CNAME` e `.nojekyll` na raiz são resto disso e continuam aqui de propósito,
para não derrubar nada antes da hora.

Quando o Railway estiver no ar e o DNS apontando para ele:

1. em **Settings → Pages** do repositório, desligue o Pages;
2. apague `CNAME` e `.nojekyll`.

Se precisar voltar ao site estático antigo por algum motivo, ele está inteiro
no commit `76675f3` — dá para publicar de novo apontando o Pages para uma
branch criada dali:

```bash
git branch site-antigo 76675f3
git push origin site-antigo
```

---

## Estrutura

```
manage.py
Procfile                 comandos que o Railway roda (migrate + gunicorn)
requirements.txt
.python-version
.env.example

config/
  settings.py            tudo que varia entre máquinas vem de variável de ambiente
  urls.py

eventos/
  models.py              Area, Evento e a função areas_do_usuario()
  views.py               site público e painel
  forms.py               formulário de evento (limita as áreas do usuário)
  admin.py               Django Admin, incluindo o campo de áreas no usuário
  tests.py               36 testes, sobretudo de permissão
  migrations/
    0001_initial.py
    0002_areas_iniciais.py   cria os cursos/áreas da semana

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
- contato da comissão organizadora;
- links de inscrição do SUAP que ainda não abriram.

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
