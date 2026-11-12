"""
Modelo de recomendação híbrido.

Combina três sinais:
  1. Filtragem colaborativa item-item (similaridade de cosseno entre colunas da
     matriz item x usuário, com as notas centralizadas pela média de cada usuário).
  2. Filtragem baseada em conteúdo (TF-IDF dos gêneros + perfil do usuário montado
     a partir das notas que ele deu e dos gêneros preferidos declarados).
  3. Popularidade (média bayesiana) como fallback para cold start.

No modo híbrido, o peso da parte colaborativa cresce com o número de avaliações
do usuário: alpha = min(1, n_avaliacoes / cf_full_weight_at). Assim, usuários
novos recebem recomendações guiadas por conteúdo e, conforme avaliam mais
filmes, o sistema passa a confiar mais no comportamento de usuários parecidos.

Cada recomendação traz um campo `reason` explicando de onde ela veio.
Este módulo não conhece o banco de dados: recebe DataFrames e é testável isoladamente.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

STRATEGIES = ("hybrid", "collaborative", "content", "popular")
_EPS = 1e-9


@dataclass
class Recommendation:
    item_id: int
    score: float
    reason: str


def _minmax(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Normaliza para [0, 1] considerando apenas as posições candidatas (mask=True)."""
    out = np.zeros_like(values, dtype=float)
    if not mask.any():
        return out
    v = values[mask]
    lo, hi = v.min(), v.max()
    if hi - lo < _EPS:
        out[mask] = 0.0 if hi <= 0 else 1.0
    else:
        out[mask] = (v - lo) / (hi - lo)
    return out


class HybridRecommender:
    def __init__(self, cf_full_weight_at: int = 20, popularity_prior: int = 5):
        self.cf_full_weight_at = max(1, cf_full_weight_at)
        self.popularity_prior = popularity_prior
        self.is_fitted = False

    # ------------------------------------------------------------------ treino
    def fit(self, items: pd.DataFrame, ratings: pd.DataFrame) -> "HybridRecommender":
        """
        items:   colunas item_id, title, genres ("A|B|C")
        ratings: colunas user_id, item_id, rating
        """
        self.items = items.reset_index(drop=True).copy()
        self.items["genres"] = self.items["genres"].fillna("").replace("(no genres listed)", "")
        self.item_ids = self.items["item_id"].to_numpy()
        self.item_index = {int(iid): i for i, iid in enumerate(self.item_ids)}
        self.titles = dict(zip(self.items["item_id"].astype(int), self.items["title"]))
        n_items = len(self.items)

        # --- conteúdo: TF-IDF sobre os gêneros (cada gênero vira um token)
        self.vectorizer = TfidfVectorizer(token_pattern=r"[^|]+", lowercase=True)
        try:
            self.content_matrix = self.vectorizer.fit_transform(self.items["genres"])
            self.feature_names = np.array(self.vectorizer.get_feature_names_out())
        except ValueError:  # nenhum item tem gênero
            self.content_matrix = None
            self.feature_names = np.array([])

        # --- colaborativa: matriz item x usuário com notas centralizadas
        r = ratings[ratings["item_id"].isin(self.item_index.keys())].copy()
        self.user_ratings: dict[int, dict[int, float]] = {
            int(uid): dict(zip(g["item_id"].astype(int), g["rating"].astype(float)))
            for uid, g in r.groupby("user_id")
        }
        user_ids = sorted(self.user_ratings)
        user_index = {uid: j for j, uid in enumerate(user_ids)}
        if len(r):
            means = r.groupby("user_id")["rating"].transform("mean")
            centered = (r["rating"] - means).to_numpy(dtype=float)
            rows = r["item_id"].map(self.item_index).to_numpy()
            cols = r["user_id"].map(user_index).to_numpy()
            self.item_user = csr_matrix((centered, (rows, cols)), shape=(n_items, len(user_ids)))
        else:
            self.item_user = csr_matrix((n_items, 0))

        # --- popularidade: média bayesiana (evita que 1 nota 5.0 domine o ranking)
        global_mean = float(r["rating"].mean()) if len(r) else 0.0
        stats = r.groupby("item_id")["rating"].agg(["mean", "count"])
        m = self.popularity_prior
        bayes = (stats["count"] * stats["mean"] + m * global_mean) / (stats["count"] + m)
        self.popularity = np.zeros(n_items)
        self.rating_counts = np.zeros(n_items, dtype=int)
        for iid, score in bayes.items():
            self.popularity[self.item_index[int(iid)]] = score
            self.rating_counts[self.item_index[int(iid)]] = stats.loc[iid, "count"]

        self.is_fitted = True
        return self

    # ------------------------------------------------------------- componentes
    def _collaborative(self, rated: dict[int, float]):
        """Retorna (scores, índice do item avaliado que mais contribuiu) ou None."""
        if not rated or self.item_user.shape[1] == 0:
            return None
        idx = [self.item_index[i] for i in rated]
        rated_ids = list(rated)
        r = np.array([rated[i] for i in rated_ids])
        r_c = r - r.mean()
        if np.allclose(r_c, 0):  # todas as notas iguais: trata notas altas como gosto
            r_c = r - 3.0
        sims = cosine_similarity(self.item_user[idx], self.item_user)  # (k, n_items)
        sims[sims < 0] = 0.0  # só vizinhos positivamente correlacionados
        den = sims.sum(axis=0)
        if den.max() < _EPS:
            return None
        scores = (r_c @ sims) / (den + _EPS)
        contrib = sims * r_c[:, None]
        best = np.array(rated_ids)[contrib.argmax(axis=0)]
        best_val = contrib.max(axis=0)
        return scores, best, best_val

    def _content_profile(self, rated: dict[int, float], favorite_genres: list[str] | None):
        if self.content_matrix is None:
            return None
        parts = []
        if rated:
            ids = list(rated)
            r = np.array([rated[i] for i in ids])
            w = r - r.mean()
            if np.allclose(w, 0):
                w = r - 3.0
            rows = self.content_matrix[[self.item_index[i] for i in ids]]
            p = csr_matrix(w.reshape(1, -1)) @ rows
            if p.nnz and abs(p).sum() > _EPS:
                parts.append(normalize(p))
        if favorite_genres:
            g = self.vectorizer.transform(["|".join(favorite_genres)])
            if g.nnz:
                parts.append(normalize(g))
        if not parts:
            return None
        profile = parts[0]
        for extra in parts[1:]:
            profile = profile + extra
        return profile

    def _content(self, rated, favorite_genres):
        profile = self._content_profile(rated, favorite_genres)
        if profile is None:
            return None
        return cosine_similarity(profile, self.content_matrix).ravel(), profile.toarray().ravel()

    def _genre_reason(self, item_pos: int, profile_weights: np.ndarray) -> str:
        row = self.content_matrix[item_pos]
        feats = row.indices
        liked = [(profile_weights[f], self.feature_names[f]) for f in feats if profile_weights[f] > 0]
        liked.sort(reverse=True)
        if not liked:
            return "Explora gêneros novos para você"
        names = ", ".join(n.title() for _, n in liked[:2])
        return f"Combina com os gêneros que você curte: {names}"

    # ------------------------------------------------------------ recomendação
    def recommend(
        self,
        user_id: int,
        n: int = 10,
        strategy: str = "hybrid",
        favorite_genres: list[str] | None = None,
    ) -> tuple[list[Recommendation], str]:
        """Retorna (recomendações, estratégia efetivamente usada)."""
        if not self.is_fitted:
            raise RuntimeError("Modelo não treinado: chame fit() antes.")
        if strategy not in STRATEGIES:
            raise ValueError(f"Estratégia inválida: {strategy}")

        rated = self.user_ratings.get(int(user_id), {})
        candidates = np.ones(len(self.item_ids), dtype=bool)
        for iid in rated:
            candidates[self.item_index[iid]] = False
        if not candidates.any():
            return [], strategy

        cf = self._collaborative(rated) if strategy in ("hybrid", "collaborative") else None
        cb = self._content(rated, favorite_genres) if strategy in ("hybrid", "content") else None

        if strategy == "hybrid" and cf and cb:
            alpha = min(1.0, len(rated) / self.cf_full_weight_at)
            cf_part = alpha * _minmax(cf[0], candidates)
            cb_part = (1 - alpha) * _minmax(cb[0], candidates)
            scores = cf_part + cb_part
            used = "hybrid"
        elif strategy in ("hybrid", "collaborative") and cf:
            scores, used = _minmax(cf[0], candidates), "collaborative"
            cf_part, cb_part = scores, 0.0
        elif strategy in ("hybrid", "content") and cb:
            scores, used = _minmax(cb[0], candidates), "content"
            cf_part, cb_part = 0.0, scores
        else:
            scores, used = _minmax(self.popularity, candidates), "popular"
            cf_part = cb_part = 0.0

        # desempate leve por popularidade
        scores = scores + 1e-3 * _minmax(self.popularity, candidates)
        scores = np.where(candidates, scores, -np.inf)
        top = np.argsort(-scores, kind="stable")[: min(n, int(candidates.sum()))]

        recs = []
        for pos in top:
            cf_v = cf_part[pos] if isinstance(cf_part, np.ndarray) else 0.0
            cb_v = cb_part[pos] if isinstance(cb_part, np.ndarray) else 0.0
            if used == "popular":
                reason = f"Popular entre os usuários ({self.rating_counts[pos]} avaliações)"
            elif cf is not None and cf_v >= cb_v and cf[2][pos] > 0:
                reason = f"Porque você gostou de \"{self.titles[int(cf[1][pos])]}\""
            elif cb is not None:
                reason = self._genre_reason(pos, cb[1])
            else:
                reason = "Usuários com gosto parecido avaliaram bem"
            recs.append(
                Recommendation(int(self.item_ids[pos]), round(float(min(scores[pos], 1.0)), 4), reason)
            )
        return recs, used

    def similar_items(self, item_id: int, n: int = 10) -> list[Recommendation]:
        """Itens parecidos: média entre similaridade de conteúdo e de avaliações."""
        if item_id not in self.item_index:
            return []
        pos = self.item_index[item_id]
        mask = np.ones(len(self.item_ids), dtype=bool)
        mask[pos] = False
        parts, weights = [], []
        if self.content_matrix is not None:
            parts.append(cosine_similarity(self.content_matrix[pos], self.content_matrix).ravel())
            weights.append(0.5)
        if self.item_user.shape[1] and self.item_user[pos].nnz:
            parts.append(np.clip(cosine_similarity(self.item_user[pos], self.item_user).ravel(), 0, None))
            weights.append(0.5)
        if not parts:
            return []
        total = sum(w * _minmax(p, mask) for w, p in zip(weights, parts)) / sum(weights)
        total = np.where(mask, total, -np.inf)
        top = np.argsort(-total, kind="stable")[: min(n, int(mask.sum()))]
        title = self.titles[item_id]
        return [
            Recommendation(int(self.item_ids[p]), round(float(total[p]), 4), f"Parecido com \"{title}\"")
            for p in top
        ]
