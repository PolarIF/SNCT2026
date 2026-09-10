# Como colocar o site da SNCT no ar

Site da Semana Nacional de Ciência e Tecnologia do IFRO Campus Ariquemes.
Aplicação Django em container, com PostgreSQL e certificado HTTPS automático.

Este documento é para quem administra o servidor. Quem vai **usar** o site
(organização da SNCT e coordenações) só precisa da seção
[Depois que estiver no ar](#depois-que-estiver-no-ar).

---

## O que o servidor precisa ter

- **Docker** com o plugin **Compose** (`docker compose version` tem que responder)
- **Portas 80 e 443** livres para este serviço
- O domínio **snctifroari.online** apontando (registro A) para o IP deste servidor
- Cerca de 1 GB de disco e 1 GB de memória

O certificado HTTPS é emitido sozinho pelo Let's Encrypt na primeira subida.
Para isso funcionar, **o DNS já precisa estar apontando para cá** — senão a
emissão falha e o site sobe sem certificado.

---

## Subir pela primeira vez

```bash
git clone https://github.com/PolarIF/SNCT2026.git
cd SNCT2026

cp .env.producao.exemplo .env
nano .env          # preencha os campos vazios, ver abaixo

docker compose up -d --build
```

A primeira subida demora alguns minutos, porque constrói a imagem. As
seguintes são rápidas.

### O que preencher no `.env`

| Campo | O que é |
|---|---|
| `DOMINIO` | `snctifroari.online` |
| `EMAIL_CERTIFICADO` | um e-mail que receba os avisos de vencimento do certificado |
| `ALLOWED_HOSTS` | `snctifroari.online,www.snctifroari.online` |
| `SECRET_KEY` | chave aleatória, gerada com o comando abaixo |
| `POSTGRES_PASSWORD` | senha do banco; só é usada entre os containers |
| `ADMIN_USUARIO` / `ADMIN_SENHA` | a primeira conta de administrador do site |

Para gerar a `SECRET_KEY` e a senha do banco:

```bash
docker run --rm python:3.13-slim python -c "import secrets; print(secrets.token_urlsafe(50))"
```

O `.env` tem senhas dentro. Ele já está no `.gitignore`, mas convém deixá-lo
só para o dono: `chmod 600 .env`.

### Conferir se subiu

```bash
docker compose ps          # os três serviços em "healthy"/"running"
curl -sf https://snctifroari.online/saude/   # tem que responder: ok
```

Se algo não subir, o primeiro lugar para olhar é o log:

```bash
docker compose logs -f web
docker compose logs -f caddy     # problemas de certificado aparecem aqui
```

---

## Depois que estiver no ar

Passe estas informações para a organização da SNCT:

| Endereço | Para quê |
|---|---|
| `https://snctifroari.online/` | o site |
| `https://snctifroari.online/cronograma/` | o cronograma público |
| `https://snctifroari.online/painel/` | onde as coordenações cadastram os eventos |
| `https://snctifroari.online/admin/` | administração: contas, cursos/áreas e inscrições |

**Primeira coisa a fazer:** entrar em `/admin/` com o usuário e a senha do
`ADMIN_USUARIO`/`ADMIN_SENHA` e **trocar a senha**. Ela está escrita em texto
no `.env` do servidor.

O restante — criar contas para as coordenações, cadastrar cursos/áreas, abrir
as inscrições — está explicado no `README.md`.

---

## Manutenção

### Backup do banco

O que não pode ser perdido é o banco: é onde estão o cronograma, as contas e
os links de inscrição. Um backup é um comando:

```bash
docker compose exec -T db pg_dump -U snct snct | gzip > snct-$(date +%F).sql.gz
```

Vale deixar isso num cron diário, guardando fora deste servidor. Perto da
semana do evento, quando as coordenações estiverem cadastrando tudo, vale
rodar mais de uma vez por dia.

Para restaurar:

```bash
gunzip -c snct-2026-10-20.sql.gz | docker compose exec -T db psql -U snct -d snct
```

### Atualizar o site

```bash
git pull
docker compose up -d --build
```

As migrações do banco rodam sozinhas quando o container sobe. Nada se perde.

### Reiniciar

```bash
docker compose restart
```

Subir de novo é seguro a qualquer momento: as migrações e a criação do
administrador são idempotentes, e trocar a senha pelo site não é desfeito.

### O que NÃO fazer

**Nunca rode `docker compose down -v`.** O `-v` apaga os volumes, e com eles o
banco inteiro e os certificados. Para parar sem perder nada:

```bash
docker compose down          # sem o -v
```

---

## Se a TI já tem um proxy na frente

Quando as portas 80 e 443 já são de outro serviço (um nginx do campus, por
exemplo), o Caddy daqui não deve subir. Nesse caso:

1. Apague o serviço `caddy` inteiro do `docker-compose.yml`, junto com os
   volumes `caddy_data` e `caddy_config`.
2. No serviço `web`, troque `expose: ["8000"]` por:

   ```yaml
   ports:
     - "127.0.0.1:8000:8000"
   ```

3. No proxy existente, aponte para `127.0.0.1:8000` e **repasse o cabeçalho
   `X-Forwarded-Proto`**. Em nginx:

   ```nginx
   location / {
       proxy_pass http://127.0.0.1:8000;
       proxy_set_header Host              $host;
       proxy_set_header X-Forwarded-Proto $scheme;
       proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
   }
   ```

Sem o `X-Forwarded-Proto`, o Django acha que a requisição chegou em HTTP e
redireciona para HTTPS em laço infinito — o sintoma é o navegador dizendo que
a página redirecionou vezes demais. Se o proxy não puder mandar esse
cabeçalho, ponha `HTTPS_ATIVO=0` no `.env` como último recurso, sabendo que
aí a senha do painel trafega em texto claro entre o proxy e a aplicação.

---

## Sem PostgreSQL

Se por algum motivo for melhor rodar só um container, a aplicação funciona
com SQLite num volume. Apague os serviços `db` e `caddy` do compose, tire o
`depends_on` e a linha `DATABASE_URL` do serviço `web`, e ponha no `.env`:

```
DATABASE_URL=sqlite:////dados/db.sqlite3
```

São quatro barras: três da URL e uma do caminho absoluto. O volume `dados`
já está declarado no compose e é onde o arquivo fica. Para o tamanho deste
site — sete coordenações e algumas centenas de atividades — o SQLite dá conta
com folga. O backup passa a ser copiar esse arquivo.

---

## Resolução de problemas

**O site não abre e o `docker compose ps` mostra `web` reiniciando**
`docker compose logs web`. Quase sempre é `.env` incompleto: a aplicação se
recusa a subir sem `SECRET_KEY`, e diz isso na primeira linha do erro.

**Erro 400 em toda página**
O domínio usado no navegador não está em `ALLOWED_HOSTS`. Acrescente e
`docker compose up -d`.

**O certificado não sai**
`docker compose logs caddy`. Confirme que o DNS já aponta para este servidor
(`dig +short snctifroari.online`) e que a porta 80 chega de fora — o
Let's Encrypt valida por ela.

**"Redirecionou vezes demais"**
Falta o `X-Forwarded-Proto` do proxy da frente. Veja a seção acima.

**Erro 403 ao salvar um formulário**
`CSRF_TRUSTED_ORIGINS`. Acontece quando o site está sendo servido em `http://`
mas a configuração espera `https://`. Corrija o esquema no `.env`.
