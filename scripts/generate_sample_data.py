"""
Gera um conjunto de dados pequeno, no formato MovieLens, em data/sample/.

Serve para a aplicação subir funcionando sem precisar baixar nada e para os testes.
Os usuários sintéticos têm "perfis de gosto" por gênero, então os padrões que o
modelo deve aprender são conhecidos e reprodutíveis (semente fixa).

Uso:  python scripts/generate_sample_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "data" / "sample"

MOVIES = [
    ("Toy Story (1995)", "Adventure|Animation|Children|Comedy|Fantasy"),
    ("Shrek (2001)", "Adventure|Animation|Children|Comedy|Fantasy|Romance"),
    ("Finding Nemo (2003)", "Adventure|Animation|Children|Comedy"),
    ("Up (2009)", "Adventure|Animation|Children|Drama"),
    ("Inside Out (2015)", "Adventure|Animation|Children|Comedy|Drama|Fantasy"),
    ("Coco (2017)", "Adventure|Animation|Children"),
    ("The Lion King (1994)", "Adventure|Animation|Children|Drama|Musical"),
    ("Spirited Away (2001)", "Adventure|Animation|Fantasy"),
    ("The Matrix (1999)", "Action|Sci-Fi|Thriller"),
    ("Inception (2010)", "Action|Crime|Drama|Mystery|Sci-Fi|Thriller"),
    ("Interstellar (2014)", "Sci-Fi|IMAX"),
    ("Blade Runner (1982)", "Action|Sci-Fi|Thriller"),
    ("Alien (1979)", "Horror|Sci-Fi"),
    ("Star Wars: Episode IV - A New Hope (1977)", "Action|Adventure|Sci-Fi"),
    ("The Terminator (1984)", "Action|Sci-Fi|Thriller"),
    ("Arrival (2016)", "Sci-Fi"),
    ("The Dark Knight (2008)", "Action|Crime|Drama|IMAX"),
    ("Mad Max: Fury Road (2015)", "Action|Adventure|Sci-Fi|Thriller"),
    ("Die Hard (1988)", "Action|Crime|Thriller"),
    ("Gladiator (2000)", "Action|Adventure|Drama"),
    ("The Godfather (1972)", "Crime|Drama"),
    ("Pulp Fiction (1994)", "Comedy|Crime|Drama|Thriller"),
    ("Goodfellas (1990)", "Crime|Drama"),
    ("Se7en (1995)", "Mystery|Thriller"),
    ("Parasite (2019)", "Comedy|Drama|Thriller"),
    ("The Shining (1980)", "Horror"),
    ("Get Out (2017)", "Horror"),
    ("Hereditary (2018)", "Drama|Horror|Mystery|Thriller"),
    ("The Exorcist (1973)", "Horror|Mystery"),
    ("A Quiet Place (2018)", "Drama|Horror|Thriller"),
    ("Pride & Prejudice (2005)", "Drama|Romance"),
    ("The Notebook (2004)", "Drama|Romance"),
    ("La La Land (2016)", "Comedy|Drama|Romance"),
    ("Notting Hill (1999)", "Comedy|Romance"),
    ("Titanic (1997)", "Drama|Romance"),
    ("Before Sunrise (1995)", "Drama|Romance"),
    ("Superbad (2007)", "Comedy"),
    ("The Hangover (2009)", "Comedy|Crime"),
    ("Mean Girls (2004)", "Comedy"),
    ("The Grand Budapest Hotel (2014)", "Comedy|Drama"),
    ("Forrest Gump (1994)", "Comedy|Drama|Romance|War"),
    ("The Shawshank Redemption (1994)", "Crime|Drama"),
]

# perfis de gosto: gênero -> afinidade (-1 a 1)
PROFILES = {
    "familia": {"Animation": 1.0, "Children": 0.9, "Comedy": 0.4, "Horror": -1.0, "Crime": -0.4},
    "scifi": {"Sci-Fi": 1.0, "Action": 0.6, "Thriller": 0.3, "Romance": -0.6, "Children": -0.5},
    "crime": {"Crime": 1.0, "Thriller": 0.7, "Drama": 0.4, "Children": -0.8, "Musical": -0.6},
    "terror": {"Horror": 1.0, "Thriller": 0.6, "Mystery": 0.5, "Romance": -0.5, "Children": -0.7},
    "romance": {"Romance": 1.0, "Drama": 0.5, "Comedy": 0.4, "Horror": -1.0, "Action": -0.4},
    "comedia": {"Comedy": 1.0, "Romance": 0.2, "Horror": -0.6, "Sci-Fi": -0.3},
}


def main(n_users: int = 36, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    OUT.mkdir(parents=True, exist_ok=True)
    movies = pd.DataFrame(
        {"movieId": range(1, len(MOVIES) + 1), "title": [m[0] for m in MOVIES], "genres": [m[1] for m in MOVIES]}
    )
    names = list(PROFILES)
    rows = []
    for user_id in range(1, n_users + 1):
        profile = PROFILES[names[(user_id - 1) % len(names)]]
        seen = rng.choice(len(movies), size=rng.integers(10, 22), replace=False)
        for idx in seen:
            genres = movies.loc[idx, "genres"].split("|")
            affinity = np.mean([profile.get(g, 0.0) for g in genres])
            score = 3.0 + 2.2 * affinity + rng.normal(0, 0.45)
            rating = float(np.clip(np.round(score * 2) / 2, 0.5, 5.0))
            rows.append((user_id, int(movies.loc[idx, "movieId"]), rating, 1700000000 + len(rows)))
    ratings = pd.DataFrame(rows, columns=["userId", "movieId", "rating", "timestamp"])
    movies.to_csv(OUT / "movies.csv", index=False)
    ratings.to_csv(OUT / "ratings.csv", index=False)
    print(f"{len(movies)} filmes e {len(ratings)} avaliações de {n_users} usuários em {OUT}")


if __name__ == "__main__":
    main()
