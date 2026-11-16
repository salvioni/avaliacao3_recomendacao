# 🎬 Próxima Sessão — Sistema de Recomendação de Filmes

API de recomendação de filmes construída com **FastAPI**, **PostgreSQL** e **Docker**.
O modelo é **híbrido**: combina filtragem colaborativa item-item com filtragem baseada
em conteúdo e se adapta à quantidade de informação que o sistema tem sobre cada usuário.
Toda recomendação vem com uma **explicação** ("Porque você gostou de *Get Out*").

| | |
|---|---|
| **Dataset** | MovieLens (GroupLens) + conjunto de exemplo no mesmo formato |
| **Modelo** | Híbrido: colaborativa item-item + conteúdo (TF-IDF de gêneros) + popularidade bayesiana |
| **API** | FastAPI, com documentação automática em `/docs` (Swagger UI) e `/redoc` |
| **Banco** | PostgreSQL (Docker) ou SQLite (execução local) via SQLAlchemy 2 |
| **Testes** | 31 testes com pytest (unitários do modelo + integração da API) |

---

## Sumário
1. [Como executar](#1-como-executar)
2. [Endpoints](#2-endpoints)
3. [Exemplo de uso](#3-exemplo-de-uso)
4. [O modelo de recomendação](#4-o-modelo-de-recomendação)
5. [Decisões de design](#5-decisões-de-design)
6. [Dados](#6-dados)
7. [Testes](#7-testes)
8. [Estrutura do projeto](#8-estrutura-do-projeto)

---

## 1. Como executar

### Opção A: Docker (recomendado)

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e aberto.

```bash
git clone https://github.com/salvioni/avaliacao3_recomendacao.git
cd avaliacao3_recomendacao
docker compose up --build
```

Isso sobe dois serviços:
- `db`: PostgreSQL 16
- `api`: a aplicação, em http://localhost:8000

Na primeira execução o banco é populado automaticamente com os dados de exemplo.
Abra **http://localhost:8000/docs** para testar a API pelo Swagger.

Rodar os testes dentro do container:
```bash
docker compose run --rm api pytest -v
```

Parar e apagar os dados do banco:
```bash
docker compose down -v
```

> No Linux/macOS também dá para usar `./scripts/docker_up.sh`, que sobe tudo e espera a API ficar saudável.

### Opção B: Local, sem Docker (usa SQLite)

Pré-requisito: Python 3.11 ou superior.

**Linux / macOS / WSL**
```bash
./scripts/install.sh      # cria .venv e instala dependências
./scripts/run.sh          # sobe a API em http://localhost:8000
./scripts/test.sh         # roda os testes
```

**Windows (PowerShell)**
```powershell
.\scripts\install.ps1
.\scripts\run.ps1
python -m pytest -v
```

> Se o PowerShell bloquear os scripts, rode antes: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Usando o MovieLens completo

```bash
python scripts/download_movielens.py    # baixa para data/movielens/
```

- **Docker:** `docker compose down -v` e depois `SEED_DIR=/app/data/movielens docker compose up --build`
  (no PowerShell: `$env:SEED_DIR="/app/data/movielens"; docker compose up --build`)
- **Local:** apague `recsys.db` e rode com `SEED_DIR=data/movielens ./scripts/run.sh`

O seed só acontece quando o banco está vazio.

### Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./recsys.db` | URL do banco (no Compose aponta para o PostgreSQL) |
| `SEED_ON_STARTUP` | `true` | Popula o banco na inicialização se estiver vazio |
| `SEED_DIR` | `data/sample` | Pasta com `movies.csv` e `ratings.csv` |
| `CF_FULL_WEIGHT_AT` | `20` | Nº de avaliações a partir do qual a colaborativa tem peso total |

---

## 2. Endpoints

| Método | Rota | Descrição | Requisito do enunciado |
|---|---|---|---|
| `POST` | `/users` | Cria usuário (nome + gêneros favoritos) | Adicionar usuários |
| `GET` | `/users` · `/users/{id}` | Lista / detalha usuários | |
| `POST` | `/items` | Cria filme (título + gêneros) | Adicionar itens |
| `GET` | `/items` · `/items/{id}` | Lista (busca por `q` e `genre`) / detalha filmes | |
| `PUT` | `/users/{id}/preferences` | Atualiza gêneros favoritos e várias avaliações de uma vez | Atualizar preferências |
| `POST` | `/users/{id}/ratings` | Avalia um filme (nota de 0.5 a 5; se já existe, atualiza) | Atualizar preferências |
| `GET` | `/users/{id}/ratings` | Lista as avaliações do usuário | |
| `DELETE` | `/users/{id}/ratings/{item_id}` | Remove uma avaliação | |
| `GET` | `/users/{id}/recommendations` | **Recomendações** (`n`, `strategy`) | Obter recomendações |
| `GET` | `/items/{id}/similar` | Filmes parecidos com um filme | Extra |
| `GET` | `/health` | Verifica API e banco | |

`strategy` aceita: `hybrid` (padrão), `collaborative`, `content` e `popular`.
A resposta informa também `strategy_used`, a estratégia efetivamente aplicada
(por exemplo, um usuário novo pedindo `hybrid` recebe `content` ou `popular`).

---

## 3. Exemplo de uso

```bash
# 1. cria um usuário novo que gosta de terror
curl -X POST localhost:8000/users -H "Content-Type: application/json" \
     -d '{"name": "Cele", "favorite_genres": ["Horror", "Thriller"]}'
# -> {"id": 37, "name": "Cele", "favorite_genres": ["Horror","Thriller"], "n_ratings": 0}

# 2. recomendações (cold start: usa os gêneros favoritos)
curl "localhost:8000/users/37/recommendations?n=3"

# 3. avalia alguns filmes
curl -X PUT localhost:8000/users/37/preferences -H "Content-Type: application/json" \
     -d '{"ratings": [{"item_id": 26, "rating": 5}, {"item_id": 31, "rating": 1.5}]}'

# 4. recomendações de novo: agora a filtragem colaborativa entra no cálculo
curl "localhost:8000/users/37/recommendations?n=3"
```

Exemplo de resposta:
```json
{
  "user_id": 4,
  "strategy": "hybrid",
  "strategy_used": "hybrid",
  "recommendations": [
    {
      "item": {"id": 13, "title": "Alien (1979)", "genres": ["Horror", "Sci-Fi"]},
      "score": 0.9999,
      "reason": "Porque você gostou de \"Get Out (2017)\""
    }
  ]
}
```

---

## 4. O modelo de recomendação

Resumo abaixo. A explicação completa, com as fórmulas, está em [`docs/modelo.md`](docs/modelo.md).

O modelo (`app/recommender.py`) combina três sinais:

**1. Filtragem colaborativa item-item**
Monta a matriz *filmes × usuários* com as notas **centralizadas pela média de cada usuário**
(assim, um usuário que dá 4 para tudo não pesa como quem dá 4 só para o que ama).
A similaridade entre filmes é o cosseno entre suas linhas. A nota prevista de um filme
é a média das notas que o usuário deu aos filmes parecidos com ele, ponderada pela similaridade.

**2. Filtragem baseada em conteúdo**
Cada filme vira um vetor TF-IDF dos seus gêneros (gêneros raros pesam mais que "Drama").
O perfil do usuário é a soma dos vetores dos filmes que ele avaliou, com peso positivo
para os que gostou e negativo para os que não gostou, somado aos gêneros favoritos que declarou.
A pontuação de um filme é o cosseno entre ele e o perfil.

**3. Popularidade (média bayesiana)**
Usada quando não há nenhuma informação sobre o usuário. A média bayesiana evita que
um filme com uma única nota 5.0 apareça no topo.

**Combinação híbrida adaptativa**
```
alpha = min(1, nº de avaliações do usuário / 20)
score = alpha · colaborativa + (1 − alpha) · conteúdo
```
Um usuário novo recebe recomendações guiadas pelo conteúdo. Conforme avalia mais filmes,
o sistema passa a confiar mais no comportamento de usuários parecidos. Isso resolve o
problema de *cold start* sem precisar de regras separadas.

**Explicabilidade**
Cada recomendação traz o motivo: o filme avaliado que mais contribuiu (colaborativa),
os gêneros em comum (conteúdo) ou o número de avaliações (popularidade).

---

## 5. Decisões de design

- **Modelo separado da API.** `HybridRecommender` recebe DataFrames e não conhece o banco.
  Isso permite testá-lo isoladamente e trocar o banco sem mexer no modelo.
- **Retreino preguiçoso.** Toda escrita (usuário, filme, avaliação) só marca o modelo como
  "desatualizado" (`app/services.py`). Ele é retreinado na próxima recomendação. As escritas
  ficam rápidas e as recomendações refletem sempre os dados mais recentes. Em um teste com
  volume equivalente ao MovieLens small (~100 mil avaliações), o treino levou cerca de 0,25 s
  e cada recomendação cerca de 30 ms.
- **Item-item em vez de user-user.** Os filmes mudam menos que os usuários, e a explicação
  "porque você gostou de X" é mais intuitiva.
- **Similaridade calculada sob demanda.** Em vez de pré-calcular a matriz filme × filme
  (9,7 mil × 9,7 mil ≈ 760 MB), o modelo calcula só as linhas dos filmes que o usuário avaliou.
- **Upsert de avaliações.** Avaliar de novo o mesmo filme atualiza a nota em vez de duplicar
  (restrição `UNIQUE(user_id, item_id)` no banco).
- **SQLite local, PostgreSQL no Docker.** O mesmo código roda nos dois, via SQLAlchemy.
  O seed corrige as sequências de ID do PostgreSQL depois de inserir IDs do MovieLens.
- **Container seguro e saudável.** A imagem roda com usuário sem root, tem `HEALTHCHECK`,
  e o Compose só sobe a API depois que o PostgreSQL responde.

---

## 6. Dados

**MovieLens** — mantido pelo [GroupLens](https://grouplens.org/datasets/movielens/)
(Universidade de Minnesota). O projeto usa a versão *ml-latest-small*
(~100 mil avaliações, 610 usuários, ~9 mil filmes), baixada por `scripts/download_movielens.py`.
O arquivo não é versionado no repositório.

> F. Maxwell Harper and Joseph A. Konstan. 2015. *The MovieLens Datasets: History and Context.*
> ACM Transactions on Interactive Intelligent Systems (TiiS) 5, 4, Article 19.

**Conjunto de exemplo (`data/sample/`)** — gerado por `scripts/generate_sample_data.py`
no mesmo formato do MovieLens. Os 42 títulos e gêneros são de filmes reais, mas **as avaliações
são sintéticas**: 36 usuários com perfis de gosto (família, ficção científica, crime, terror,
romance, comédia). Serve para a aplicação subir funcionando sem download e para os testes
terem padrões conhecidos.

---

## 7. Testes

```bash
python -m pytest -v
```

- **`tests/test_recommender.py`** (unitários): fã de animação recebe animação e fã de terror
  recebe terror em todas as estratégias; itens já avaliados nunca são recomendados;
  cold start com e sem gêneros favoritos; scores normalizados e ordenados; explicações;
  itens similares; erros.
- **`tests/test_api.py`** (integração): CRUD de usuários e filmes, validação (nota fora de
  0.5–5 → 422), upsert de avaliações, atualização de preferências, 404s, todas as estratégias,
  fluxo completo de um usuário novo e retreino após inserir um filme.

Os testes usam um SQLite temporário e não afetam o banco real.

---

## 8. Estrutura do projeto

```
├── app/
│   ├── main.py            # cria o FastAPI, inicialização e /health
│   ├── config.py          # variáveis de ambiente
│   ├── database.py        # conexão SQLAlchemy
│   ├── models.py          # tabelas: users, items, ratings
│   ├── schemas.py         # schemas Pydantic (entrada/saída da API)
│   ├── crud.py            # operações de banco
│   ├── recommender.py     # ⭐ o modelo híbrido
│   ├── services.py        # mantém o modelo treinado em memória
│   ├── seed.py            # carga inicial a partir dos CSVs
│   └── routers/
│       ├── users.py       # usuários, avaliações, preferências, recomendações
│       └── items.py       # filmes e similares
├── data/sample/           # dataset de exemplo (formato MovieLens)
├── docs/modelo.md         # explicação detalhada do modelo
├── scripts/               # instalação, execução, testes, download e geração de dados
├── tests/                 # testes unitários e de integração
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```
