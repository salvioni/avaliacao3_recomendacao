"""Testes unitários do modelo (sem API e sem banco)."""
import pytest

from app.recommender import HybridRecommender


@pytest.fixture
def model(toy_data):
    items, ratings = toy_data
    return HybridRecommender(cf_full_weight_at=3).fit(items, ratings)


@pytest.mark.parametrize("strategy", ["hybrid", "collaborative", "content"])
def test_fa_de_animacao_recebe_animacao(model, strategy):
    recs, _ = model.recommend(user_id=1, n=1, strategy=strategy)
    assert recs[0].item_id == 3  # única animação que o usuário 1 ainda não viu


@pytest.mark.parametrize("strategy", ["hybrid", "collaborative", "content"])
def test_fa_de_terror_recebe_terror(model, strategy):
    recs, _ = model.recommend(user_id=3, n=1, strategy=strategy)
    assert recs[0].item_id == 6


def test_nunca_recomenda_itens_ja_avaliados(model, toy_data):
    _, ratings = toy_data
    for uid in ratings["user_id"].unique():
        seen = set(ratings.loc[ratings.user_id == uid, "item_id"])
        recs, _ = model.recommend(user_id=int(uid), n=10)
        assert seen.isdisjoint(r.item_id for r in recs)


def test_cold_start_sem_dados_usa_popularidade(model):
    recs, used = model.recommend(user_id=999, n=3)
    assert used == "popular"
    assert len(recs) == 3
    assert "Popular" in recs[0].reason


def test_cold_start_com_generos_favoritos_usa_conteudo(model):
    recs, used = model.recommend(user_id=999, n=3, favorite_genres=["Horror"])
    assert used == "content"  # híbrido sem sinal colaborativo cai para conteúdo
    assert {r.item_id for r in recs} == {4, 5, 6}
    assert "Horror" in recs[0].reason


def test_scores_normalizados_e_ordenados(model):
    recs, _ = model.recommend(user_id=1, n=3)
    scores = [r.score for r in recs]
    assert all(0 <= s <= 1 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_explicacao_colaborativa_cita_filme_avaliado(model):
    recs, _ = model.recommend(user_id=1, n=1, strategy="collaborative")
    assert recs[0].reason.startswith("Porque você gostou de")


def test_itens_similares(model):
    similar = model.similar_items(item_id=4, n=2)
    assert {s.item_id for s in similar} == {5, 6}
    assert all(s.item_id != 4 for s in similar)


def test_estrategia_invalida(model):
    with pytest.raises(ValueError):
        model.recommend(user_id=1, strategy="aleatoria")


def test_modelo_nao_treinado():
    with pytest.raises(RuntimeError):
        HybridRecommender().recommend(user_id=1)


def test_funciona_sem_avaliacoes_no_sistema(toy_data):
    items, ratings = toy_data
    model = HybridRecommender().fit(items, ratings.iloc[0:0])
    recs, used = model.recommend(user_id=1, n=2, favorite_genres=["Animation"])
    assert used == "content"
    assert recs[0].item_id in {1, 2, 3}
