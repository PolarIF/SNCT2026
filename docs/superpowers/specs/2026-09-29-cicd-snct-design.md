# CI/CD do site da SNCT — desenho

**Data:** 2026-09-29
**Estado:** aprovado, aguardando plano de implementação

## Por que

O deploy hoje é `git pull && docker compose up -d --build` dentro da VPS. Isso
tem quatro problemas, e todos pesam:

1. **A VPS constrói a imagem.** Ela divide disco com três runners de CI do
   ANESP; medimos pressão de I/O de 98% em horário de build. A construção
   compete com a produção do ANESP e do Rota Rural.
2. **Deployar exige terminal.** Durante a semana do evento, um ajuste de
   cronograma pode precisar entrar com a pessoa longe do computador.
3. **Os testes só rodam se alguém lembrar.** São 134. Um PR pode entrar na
   `main` quebrado e só descobrirmos no deploy.
4. **Voltar atrás é lento.** Hoje significa `git checkout` do commit anterior e
   reconstruir na VPS — minutos, justamente quando o site está ruim.

Em uma frase: **praticidade e rapidez**.

## O que muda

A imagem passa a ser construída no GitHub Actions e publicada no GHCR. A VPS
deixa de construir e passa a puxar. O deploy continua manual, disparado por
conversa no grupo do Telegram, através do bot de ops que já existe.

## Decisões tomadas

| Questão | Decisão |
|---|---|
| Quando publicar | a cada push na `main`, depois dos testes passarem |
| Como marcar | `sha-<short>` (imutável) + `latest` (móvel) |
| Visibilidade do pacote | público — a VPS puxa sem token |
| Quem dispara o deploy | Eduardo e Julio |
| Como dispara | pelo agente do Telegram, que **invoca scripts**, nunca comandos |
| Onde mora a config de produção | no `.env` e no override da VPS, fora do git |
| Deploy automático no merge | não — o disparo é sempre humano |

## Arquitetura

### 1. Pipeline no GitHub

Arquivo único: `.github/workflows/ci.yml`.

| Evento | Roda |
|---|---|
| `pull_request` para `main` | testes |
| `push` na `main` | testes → build → publica |

O job de publicação declara `needs: testes`. Um merge que quebre a suíte não
gera imagem, então nunca existe imagem deployável quebrada.

**Os testes rodam contra PostgreSQL 17**, como service container — não SQLite.
O Django cai em SQLite quando não há `DATABASE_URL`, mas produção é Postgres, e
é em migração que os dois divergem. O container custa poucos segundos.

**`collectstatic` roda antes dos testes.** Com `DEBUG=0` o whitenoise usa
`CompressedManifestStaticFilesStorage`; sem o manifest, a suíte quebra inteira
com `Missing staticfiles manifest entry`. Sem essa etapa o CI falharia sempre e
pareceria defeito do código.

**Duas tags por publicação:**

```
ghcr.io/polarif/snct2026:sha-543677d    imutável — é o que permite voltar atrás
ghcr.io/polarif/snct2026:latest         move a cada push na main
```

A imagem carrega `LABEL org.opencontainers.image.revision=<sha>`. É esse rótulo
que deixa o deploy de `latest` registrar no histórico **qual SHA** subiu — sem
ele, "latest" no histórico não significaria nada uma semana depois.

O job de publicação precisa de `permissions: { contents: read, packages: write }`
e autentica no GHCR com o `GITHUB_TOKEN` da própria execução — não há segredo a
criar nem a rotacionar.

Cache de layers entre execuções, para o `pip install` não repetir a cada push.

### 2. Consumo na VPS

A tag corrente é uma variável; o override aponta para ela:

```yaml
# ~/snct2026/docker-compose.override.yml (não versionado)
services:
  web:
    image: ghcr.io/polarif/snct2026:${SNCT_TAG:?defina SNCT_TAG no .env}
    ports:
      - "127.0.0.1:8040:8000"
  caddy:
    profiles: ["desativado"]
```

```bash
# ~/snct2026/.env
SNCT_TAG=sha-543677d
```

Deployar é escrever uma tag no `.env`, puxar e subir. Voltar atrás é o mesmo
mecanismo com outra tag — mesmo código, mesmo caminho testado.

O `docker-compose.yml` versionado **não muda**: continua com `build: .`, então
quem clona e desenvolve não sente diferença.

> **Armadilha a documentar:** o override não consegue apagar a chave `build`.
> Ela fica inerte, mas `docker compose up -d --build` na VPS reconstrói local e
> **sobrescreve a imagem puxada**, sem erro — o site segue no ar rodando algo
> que não veio do CI. Os scripts nunca passam `--build`, e isso vai no README
> do `telegram-ops` e no `SNCT-TEMPORARIO.md`.

**Histórico:** `~/snct2026/.deploy-historico`, uma linha por deploy com data,
SHA, quem disparou e o resultado. É dele que o rollback lê a versão anterior, e
é ele que responde "o que está rodando e desde quando".

### 3. Scripts de operação

Ficam em `~/telegram-ops/bin/`, junto de `alertas`, `targets` e `janelas`: é
onde a allowlist do agente aponta (`Bash(/home/eduardo/telegram-ops/bin/*)`) e
são scripts de operação da máquina, não do produto.

| script | faz |
|---|---|
| `deploy [sha]` | atualiza produção; `latest` se sem argumento |
| `rollback [sha]` | volta à versão anterior, ou a um SHA dado |
| `versoes [n]` | imagens disponíveis no GHCR, qual roda agora, últimos deploys |

Fluxo do `deploy`:

1. valida que a tag existe no GHCR
2. guarda a tag atual
3. `docker compose pull web`
4. escreve `SNCT_TAG` no `.env`
5. `docker compose up -d web` — **sem `--build`**
6. aguarda `healthy`, limite de 90s
7. sucesso: registra no histórico e responde SHA + tempo
8. falha: **volta sozinho** para a tag anterior, registra e relata

`rollback` é o mesmo fluxo com a tag lida do histórico.

### 4. Salvaguardas

O agente é quem invoca os scripts, então parte da proteção não pode depender do
julgamento dele.

**a) Permissão verificada fora do modelo.** O daemon sabe quem mandou a
mensagem e exporta `DEPLOY_PERMITIDO=1|0` no ambiente do processo. O script lê
e recusa se for `0`, independentemente do que o agente tenha concluído. A lista
de quem deploya é decidida por código.

A lista mora em `DEPLOY_USER_IDS`, no `~/telegram-ops/config.env`, **separada
da `USER_IDS`** que controla quem conversa com o bot. Hoje as duas têm as
mesmas pessoas (Eduardo `5845285858` e Julio `6372946729`, ambos já ativos),
mas separá-las permite dar consulta a alguém sem dar deploy — e é a lista de
deploy que precisa ser a restritiva.

**b) Dois passos.** Sem `--sim`, `deploy` é dry-run: mostra tag atual, tag alvo,
commits de diferença e **se há migrações entre as versões**. Só com `--sim` age.
O system prompt instrui a mostrar o dry-run antes e aplicar após confirmação; o
contexto por reply do bot é o que sustenta essa conversa.

> Limite honesto: esta salvaguarda depende do modelo. Um "sobe agora, pode
> aplicar" leva direto ao `--sim`, e está certo. Ela previne disparo por
> ambiguidade, não por instrução clara. As salvaguardas (a) e (c) não dependem
> de julgamento.

**c) Um deploy a cada 2 minutos**, no máximo. Trava contra repetição acidental.

Somadas ao que já existe — allowlist de quem fala com o bot, log de auditoria,
redação de segredos na saída — o pior caso de uma interpretação errada é: subir
uma versão que já passou nos testes, e que volta sozinha se não ficar de pé.

## Limites conhecidos

**Rollback não desfaz migração.** O `entrypoint.sh` roda `migrate` a cada start.
Se a versão nova migrar e você voltar, o banco fica com o schema novo e a versão
antiga pode não funcionar com ele. Por isso o dry-run avisa quando há migrações:
para você saber que aquele deploy é de mão única **antes** de aplicar. Reverter
schema é operação manual.

**Cada deploy derruba o site por ~15–30s** — menos que os minutos de hoje, e
abaixo do `for: 2m` dos alertas, então um deploy normal **não dispara alerta
falso**. Aparece no `janelas` como janela curta, como os rebuilds já aparecem.

## Fora de escopo

- **Deploy automático no merge** — decidir quando a mudança entra vale mais,
  durante o evento, que economizar um comando.
- **Staging** — não há ambiente e o site é temporário; os testes no CI cobrem.
- **Zero-downtime (blue-green)** — 15 segundos não justificam dois containers e
  troca de proxy.
- **Limpeza de imagens antigas no GHCR** — acumulam devagar, uma por merge.
  Resolve-se com política de retenção se incomodar; não vale código agora.

## Como validar

Fazendo, não inspecionando: um deploy real de uma versão conhecida, um rollback
real de volta, e conferindo por `janelas` e `erros` que o site voltou íntegro —
o mesmo método que validou a correção do cAdvisor e a do multiproc.
