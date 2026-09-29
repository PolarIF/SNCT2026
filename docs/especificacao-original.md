# Prompt para Claude Code — Backend e painel de cronograma da SNCT IFRO Ariquemes

## Contexto

Estou desenvolvendo o site da SNCT do IFRO Campus Ariquemes:

**Domínio:** `snctifroari.online`

O projeto atual é um site simples feito em HTML, CSS e JavaScript e hospedado no GitHub Pages.

Quero evoluir o projeto para permitir que eu e as coordenações dos cursos gerenciem o cronograma/eventos sem precisar editar o código toda vez que houver uma alteração de última hora.

A prioridade é **simplicidade, facilidade de manutenção e facilidade de uso**, e não construir um sistema empresarial complexo.

---

# Objetivo

Transformar o projeto atual em uma aplicação web com backend e banco de dados, mantendo a aparência atual do site público praticamente intacta.

O sistema deverá ter:

1. Site público da SNCT.
2. Página pública de cronograma/calendário.
3. Sistema de login.
4. Painel simples para gerenciamento de eventos.
5. Usuários vinculados a determinados cursos/áreas.
6. Um administrador principal (EU) com acesso total.
7. Possibilidade de EU criar contas e definir quais cursos/áreas cada conta pode gerenciar.
8. Possibilidade de EU cadastrar, editar e excluir qualquer evento.
9. Coordenações podendo editar somente os eventos das áreas às quais foram vinculadas.
10. Alterações feitas no painel aparecendo automaticamente no calendário público.

---

# Stack desejada

Use uma stack simples e tradicional:

- Python
- Django
- PostgreSQL
- HTML
- CSS
- JavaScript
- Django Templates
- Django ORM
- Django Authentication

Não quero React, Vue, Next.js ou outro frontend complexo neste momento.

Também não quero criar uma API desnecessariamente complexa.

Se uma API REST fizer sentido para separar melhor algumas partes, pode ser usada, mas prefira a solução mais simples possível.

O projeto deverá estar preparado para deploy no Railway.

---

# Regra mais importante

**NÃO refaça esteticamente a página principal neste momento.**

A página principal atual já existe e deve continuar visualmente como está.

Antes de alterar qualquer coisa visual importante, analise a estrutura existente do projeto.

O objetivo desta etapa é adicionar a infraestrutura dinâmica de eventos e o painel de gerenciamento.

Não quero que o Claude Code "aproveite para redesenhar o site inteiro".

---

# Primeiro passo obrigatório

Antes de modificar arquivos:

1. Analise todo o projeto atual.
2. Identifique:
   - página inicial;
   - CSS;
   - JavaScript;
   - imagens/assets;
   - estrutura de navegação;
   - página(s) relacionadas a programação/cronograma, caso já existam;
   - como o projeto atualmente funciona no GitHub Pages.
3. Identifique o que pode ser reaproveitado.
4. Não remova funcionalidades existentes sem necessidade.
5. Explique brevemente a arquitetura atual e a arquitetura proposta.
6. Só depois comece a implementação.

---

# Arquitetura desejada

Quero algo aproximadamente assim:

```text
                    SNCT IFRO
                       │
              ┌────────┴────────┐
              │                 │
           Público          Coordenação
              │                 │
              ▼                 ▼
       Site + calendário     /painel/
                                  │
                                  ▼
                              Django
                                  │
                                  ▼
                             PostgreSQL
```

O Django deve servir o site e também cuidar do backend.

Não quero manter o frontend público separado em GitHub Pages se isso complicar a arquitetura.

A aplicação deve poder rodar inteira no Railway.

---

# Modelo de dados

Crie uma estrutura simples.

## Curso/Área

Cada área que terá eventos deve ser cadastrada no sistema.

Exemplo:

```text
Curso/Área
- id
- nome
- slug
- ativo
```

Não assuma que todos os eventos necessariamente precisam pertencer a um curso específico. Se o sistema precisar de eventos gerais da SNCT, permita uma categoria/área "Geral" ou uma solução equivalente.

---

# Usuários

Quero usar o sistema de autenticação do Django.

Cada conta de coordenação deve possuir:

```text
Usuário
- username
- senha
- nome
- ativo
```

E deve existir uma relação entre usuário e áreas que ele pode administrar.

IMPORTANTE:

Um usuário pode, se necessário, administrar mais de uma área.

Exemplo:

```text
coord_1
    → ADS

coord_2
    → Informática
    → Eletrotécnica

admin
    → todas
```

Não quero criar um sistema de autenticação próprio se o Django já resolver isso.

---

# Administrador principal

EU serei o administrador principal do sistema.

Preciso conseguir:

- criar usuários;
- desativar usuários;
- redefinir/trocar senha;
- cadastrar áreas/cursos;
- editar áreas/cursos;
- definir quais áreas cada usuário pode administrar;
- criar qualquer evento;
- editar qualquer evento;
- excluir qualquer evento;
- visualizar tudo.

Pode utilizar o Django Admin para as funções administrativas internas do administrador principal.

Porém:

**não quero que as coordenações usem o Django Admin.**

---

# Painel das coordenações

Crie uma interface própria e extremamente simples.

URL sugerida:

```text
/painel/
```

O usuário deverá fazer login e então visualizar somente aquilo que ele tem permissão para administrar.

Exemplo:

```text
Olá, Coordenação de ADS

[ + Novo evento ]

Próximos eventos

15/10/2026
14:00 - Palestra sobre Inteligência Artificial
Auditório

[Editar] [Excluir]

16:00 - Workshop de Flutter
Laboratório 03

[Editar] [Excluir]
```

Se o usuário tiver duas áreas:

```text
Área:
[ ADS ▼ ]
```

ou uma visualização agrupada:

```text
ADS
----------------
eventos...

Informática
----------------
eventos...
```

Escolha a solução mais simples e intuitiva.

---

# Princípio de UX

O usuário da coordenação pode ter pouco conhecimento técnico.

Portanto, o painel deve ser extremamente óbvio.

Evite termos técnicos como:

- CRUD
- ForeignKey
- ID
- slug
- objeto
- banco
- endpoint
- relacionamento

A interface deve usar termos como:

- Evento
- Atividade
- Data
- Horário
- Local
- Curso/Área
- Editar
- Excluir
- Salvar
- Cancelar

---

# Cadastro de evento

Um evento deve possuir, no mínimo:

```text
Título
Descrição
Data
Horário de início
Horário de término
Local
Curso/Área
```

Pode incluir outros campos somente se forem realmente úteis.

Não exagere no formulário.

A ideia é que alguém consiga cadastrar um evento em poucos segundos.

---

# Edição

A coordenação deve conseguir clicar em:

```text
Editar
```

e alterar facilmente:

- título;
- descrição;
- data;
- horário;
- local;
- área.

Depois:

```text
Salvar alterações
```

---

# Exclusão

Nunca exclua imediatamente sem confirmação.

Ao clicar em excluir, mostrar algo como:

```text
Excluir evento?

Tem certeza que deseja excluir
"Palestra sobre Inteligência Artificial"?

[Cancelar] [Excluir evento]
```

---

# Permissões

Essa parte é MUITO importante.

Exemplo:

```text
Usuário:
coord_ads

Permissão:
ADS
```

Esse usuário:

- pode visualizar eventos de ADS;
- pode criar eventos de ADS;
- pode editar eventos de ADS;
- pode excluir eventos de ADS;
- NÃO pode editar eventos de Informática;
- NÃO pode editar eventos de Eletrotécnica;
- NÃO pode alterar usuários;
- NÃO pode alterar permissões;
- NÃO pode alterar configurações do sistema.

Administrador:

```text
admin
```

pode fazer tudo.

Implemente as verificações de permissão também no backend.

**Não confie apenas em esconder botões no frontend.**

Mesmo sendo um sistema simples, uma requisição manual não pode permitir que um usuário altere um evento de uma área que não possui.

---

# Calendário público

Criar ou adaptar uma página pública para mostrar os eventos.

Sugestão:

```text
/cronograma/
```

A página deve buscar os eventos cadastrados no banco e mostrar:

- data;
- horário;
- título;
- local;
- área;
- descrição quando apropriado.

Pode ter visualização:

```text
Calendário
```

e/ou:

```text
Lista
```

Escolha uma implementação simples e agradável.

O calendário público é para visitantes, então não precisa de login.

---

# Atualização automática

Se uma coordenação alterar:

```text
14:00
```

para:

```text
15:00
```

o cronograma público deve passar a mostrar:

```text
15:00
```

sem que eu precise alterar HTML ou JavaScript manualmente.

---

# Segurança

Não preciso de segurança de nível bancário.

Mas quero o básico correto:

- senhas armazenadas usando o sistema seguro do Django;
- autenticação por sessão;
- CSRF habilitado;
- autorização no backend;
- usuários não conseguem acessar dados administrativos de outras áreas;
- usuários inativos não conseguem entrar;
- páginas do painel protegidas por login.

Não implemente complexidade desnecessária.

---

# Django Admin

Use o Django Admin para mim, administrador principal.

Quero poder administrar:

```text
Usuários
Áreas/Cursos
Eventos
Permissões
```

Idealmente, o Django Admin deve ser suficiente para manutenção interna do sistema.

Não precisa personalizar muito o Django Admin nesta etapa.

---

# Banco de dados

Use PostgreSQL em produção.

Prepare o projeto para usar a variável:

```text
DATABASE_URL
```

Não coloque senha do banco diretamente no código.

Para desenvolvimento local, pode ser permitido usar SQLite caso isso facilite o setup.

---

# Railway

O projeto deverá ser preparado para deploy no Railway.

Criar/configurar o necessário para:

- `requirements.txt`;
- comando de inicialização;
- migrations;
- static files;
- variáveis de ambiente;
- configuração de produção;
- PostgreSQL via Railway.

Não quero uma configuração excessivamente complexa.

Se for necessário criar:

```text
Procfile
```

ou configuração equivalente, faça.

---

# Static files

Como o projeto atual possui CSS, JS e imagens, preserve os assets.

Configure corretamente:

```text
STATIC_URL
STATIC_ROOT
```

e o que for necessário para o Railway servir os arquivos em produção.

Não quebre o layout atual durante a migração.

---

# Domínio

O domínio final será:

```text
snctifroari.online
```

A aplicação deve funcionar preparada para domínio próprio.

Não é necessário configurar DNS automaticamente.

Apenas documente no README quais registros/configurações serão necessários no Railway.

---

# Interface do painel

Não precisa ser extremamente sofisticada.

Priorize:

1. clareza;
2. botões grandes o suficiente;
3. poucos elementos;
4. mensagens claras;
5. funcionamento em celular;
6. facilidade para alguém que não entende de tecnologia.

Exemplo de navegação:

```text
┌─────────────────────────────────────┐
│ SNCT IFRO                    Sair   │
├─────────────────────────────────────┤
│                                     │
│ Meu cronograma                      │
│                                     │
│ [+ Adicionar evento]                │
│                                     │
│ 15 OUT                              │
│                                     │
│ 14:00                               │
│ Palestra sobre IA                  │
│ Auditório                           │
│                                     │
│ [Editar]       [Excluir]            │
│                                     │
└─────────────────────────────────────┘
```

Não precisa copiar exatamente esse layout.

---

# Página pública

IMPORTANTE:

A página principal atual NÃO deve ser redesenhada.

Preserve:

- cores;
- tipografia;
- espaçamento;
- estrutura;
- navegação;
- imagens;
- identidade visual.

Somente faça as alterações necessárias para integrar o backend e adicionar o cronograma.

Se houver uma página de cronograma existente, aproveite-a em vez de criar outra sem necessidade.

---

# Estrutura sugerida

Você pode adaptar a estrutura conforme o projeto atual.

Algo próximo de:

```text
snct/
├── manage.py
├── requirements.txt
├── README.md
├── .env.example
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── ...
│
├── core/
│   ├── models.py
│   ├── views.py
│   └── ...
│
├── eventos/
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── urls.py
│   ├── admin.py
│   └── ...
│
├── templates/
│   ├── ...
│   └── painel/
│
└── static/
    ├── css/
    ├── js/
    └── images/
```

Mas **não force essa estrutura se a estrutura atual do projeto sugerir algo melhor**.

---

# O que NÃO fazer

Não quero:

- React;
- Next.js;
- Vue;
- microserviços;
- Docker obrigatório para desenvolvimento;
- Kubernetes;
- sistema de permissões absurdamente complexo;
- API gigante;
- arquitetura enterprise;
- redesign completo;
- trocar toda a identidade visual;
- Firebase sem necessidade;
- autenticação própria;
- banco NoSQL sem necessidade.

Quero uma aplicação pequena, fácil de entender e fácil de manter.

---

# Critério de sucesso

Vou considerar a implementação correta quando:

### Administrador

Eu consigo:

```text
Login
↓
Criar curso/área
↓
Criar usuário
↓
Escolher quais áreas esse usuário pode gerenciar
↓
Criar evento
↓
Editar evento
↓
Excluir evento
```

### Coordenação

A coordenação consegue:

```text
Login
↓
Ver somente suas áreas
↓
Adicionar evento
↓
Editar evento
↓
Excluir evento
```

### Visitante

O visitante consegue:

```text
Abrir snctifroari.online
↓
Abrir cronograma
↓
Ver eventos atualizados
```

Sem precisar de qualquer ação minha.

---

# Importante sobre implementação

Não tente fazer tudo de uma vez sem validar a estrutura.

Trabalhe em etapas:

## Etapa 1
Analisar o projeto atual e montar plano de migração.

## Etapa 2
Criar Django e preservar o site atual.

## Etapa 3
Configurar banco e modelos.

## Etapa 4
Implementar autenticação.

## Etapa 5
Implementar permissões.

## Etapa 6
Implementar painel das coordenações.

## Etapa 7
Implementar/adaptar cronograma público.

## Etapa 8
Configurar produção/Railway.

## Etapa 9
Testar permissões e fluxo completo.

---

# Testes obrigatórios

Teste pelo menos:

### Administrador

- consegue ver tudo;
- consegue criar usuário;
- consegue definir áreas;
- consegue editar qualquer evento;
- consegue excluir qualquer evento.

### Usuário ADS

- consegue criar evento ADS;
- consegue editar evento ADS;
- consegue excluir evento ADS;
- não consegue editar evento de outra área;
- não consegue excluir evento de outra área;
- não consegue administrar usuários.

### Usuário inativo

- não consegue entrar no painel.

### Público

- consegue ver os eventos;
- não precisa de login;
- alterações aparecem corretamente.

---

# Documentação

Ao terminar, atualize/crie um `README.md` contendo:

- como instalar localmente;
- como criar ambiente virtual;
- como instalar dependências;
- como configurar `.env`;
- como executar migrations;
- como criar superusuário;
- como iniciar o servidor;
- como fazer deploy no Railway;
- variáveis de ambiente necessárias;
- como conectar o domínio;
- como cadastrar o primeiro usuário;
- como cadastrar cursos/áreas;
- como dar acesso de uma área para uma conta.

---

# Filosofia do projeto

Este não é um SaaS.

É um sistema pequeno para uma edição da SNCT e possivelmente outras edições no futuro.

**Prefira sempre a solução mais simples que resolva o problema.**

Se existir uma solução de 50 linhas e outra de 500 linhas para fazer a mesma coisa, prefira a de 50 linhas, desde que continue organizada e segura no básico.

Também não quero abstrações criadas apenas "porque é uma boa prática".

Quero código que eu consiga abrir daqui a alguns meses e entender rapidamente.

---

# Antes de finalizar

Depois da implementação:

1. Verifique se o site atual continua funcionando.
2. Teste login.
3. Teste permissões.
4. Teste criação/edição/exclusão de eventos.
5. Teste o calendário público.
6. Rode migrations.
7. Verifique static files.
8. Verifique configuração para Railway.
9. Revise o projeto procurando erros óbvios.
10. Me mostre um resumo do que foi alterado e os comandos necessários para executar localmente e fazer deploy.

**Comece analisando o projeto existente. Não faça alterações antes dessa análise.**
