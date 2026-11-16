"""Testes de integração: exercitam a API inteira (rotas + banco + modelo)."""


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_swagger_disponivel(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/users/{user_id}/recommendations" in paths


# ------------------------------------------------------------------ itens
def test_criar_e_buscar_item(client):
    r = client.post("/items", json={"title": "Interestelar (2014)", "genres": ["Sci-Fi", "Drama"]})
    assert r.status_code == 201
    item = r.json()
    assert item["genres"] == ["Sci-Fi", "Drama"]
    assert client.get(f"/items/{item['id']}").json() == item
    assert client.get("/items", params={"q": "inter"}).json() == [item]
    assert client.get("/items", params={"genre": "Horror"}).json() == []


def test_item_inexistente(client):
    assert client.get("/items/9999").status_code == 404


# --------------------------------------------------------------- usuários
def test_criar_usuario(client):
    r = client.post("/users", json={"name": "Cele", "favorite_genres": ["Comedy"]})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Cele" and body["favorite_genres"] == ["Comedy"] and body["n_ratings"] == 0


def test_validacao_de_entrada(client):
    assert client.post("/users", json={"name": ""}).status_code == 422
    uid = client.post("/users", json={"name": "X"}).json()["id"]
    iid = client.post("/items", json={"title": "Filme"}).json()["id"]
    assert client.post(f"/users/{uid}/ratings", json={"item_id": iid, "rating": 7}).status_code == 422


def test_avaliar_atualiza_em_vez_de_duplicar(client):
    uid = client.post("/users", json={"name": "X"}).json()["id"]
    iid = client.post("/items", json={"title": "Filme"}).json()["id"]
    client.post(f"/users/{uid}/ratings", json={"item_id": iid, "rating": 2})
    client.post(f"/users/{uid}/ratings", json={"item_id": iid, "rating": 4.5})
    assert client.get(f"/users/{uid}/ratings").json() == [{"item_id": iid, "rating": 4.5}]


def test_avaliar_item_inexistente(client):
    uid = client.post("/users", json={"name": "X"}).json()["id"]
    assert client.post(f"/users/{uid}/ratings", json={"item_id": 42, "rating": 3}).status_code == 404


def test_atualizar_preferencias(seeded_client):
    c = seeded_client
    uid = c.post("/users", json={"name": "Nova"}).json()["id"]
    r = c.put(
        f"/users/{uid}/preferences",
        json={"favorite_genres": ["Horror"], "ratings": [{"item_id": 26, "rating": 5}, {"item_id": 1, "rating": 1}]},
    )
    assert r.status_code == 200
    assert r.json()["favorite_genres"] == ["Horror"] and r.json()["n_ratings"] == 2


def test_remover_avaliacao(seeded_client):
    c = seeded_client
    before = c.get("/users/1/ratings").json()
    item_id = before[0]["item_id"]
    assert c.delete(f"/users/1/ratings/{item_id}").status_code == 204
    assert len(c.get("/users/1/ratings").json()) == len(before) - 1


# ----------------------------------------------------------- recomendações
def test_recomendacoes_excluem_itens_avaliados(seeded_client):
    c = seeded_client
    seen = {r["item_id"] for r in c.get("/users/1/ratings").json()}
    body = c.get("/users/1/recommendations", params={"n": 5}).json()
    assert body["strategy"] == "hybrid"
    assert len(body["recommendations"]) == 5
    assert seen.isdisjoint(rec["item"]["id"] for rec in body["recommendations"])
    assert all(rec["reason"] for rec in body["recommendations"])


def test_todas_as_estrategias(seeded_client):
    for s in ["hybrid", "collaborative", "content", "popular"]:
        r = seeded_client.get("/users/2/recommendations", params={"strategy": s, "n": 3})
        assert r.status_code == 200, s
        assert r.json()["strategy_used"] == s
    assert seeded_client.get("/users/2/recommendations", params={"strategy": "x"}).status_code == 422


def test_fluxo_completo_novo_usuario(seeded_client):
    """Usuário novo -> cold start por gênero -> avalia filmes -> recomendações mudam."""
    c = seeded_client
    uid = c.post("/users", json={"name": "Fã de terror", "favorite_genres": ["Horror"]}).json()["id"]

    first = c.get(f"/users/{uid}/recommendations", params={"n": 3}).json()["recommendations"]
    assert all("Horror" in rec["item"]["genres"] for rec in first)

    # avalia os filmes de terror recomendados -> eles saem da lista
    for rec in first:
        c.post(f"/users/{uid}/ratings", json={"item_id": rec["item"]["id"], "rating": 5})
    second = c.get(f"/users/{uid}/recommendations", params={"n": 3}).json()["recommendations"]
    assert {r["item"]["id"] for r in first}.isdisjoint(r["item"]["id"] for r in second)


def test_novo_item_entra_nas_recomendacoes(seeded_client):
    """O modelo é retreinado após inserções: um item novo já pode ser recomendado."""
    c = seeded_client
    iid = c.post("/items", json={"title": "Terror Novo (2026)", "genres": ["Horror", "Mystery", "Thriller"]}).json()["id"]
    uid = c.post("/users", json={"name": "Y", "favorite_genres": ["Horror", "Mystery", "Thriller"]}).json()["id"]
    recs = c.get(f"/users/{uid}/recommendations", params={"n": 5, "strategy": "content"}).json()["recommendations"]
    assert iid in {r["item"]["id"] for r in recs}


def test_usuario_inexistente(seeded_client):
    assert seeded_client.get("/users/9999/recommendations").status_code == 404


def test_itens_similares(seeded_client):
    body = seeded_client.get("/items/1/similar", params={"n": 3}).json()  # Toy Story
    assert len(body["similar"]) == 3
    assert all("Animation" in s["item"]["genres"] for s in body["similar"])
