"""
Baixa o MovieLens "latest-small" (~100 mil avaliações, 9 mil filmes, 610 usuários)
do GroupLens e extrai movies.csv e ratings.csv para data/movielens/.

Uso:  python scripts/download_movielens.py
Depois rode a API com SEED_DIR=data/movielens (em um banco vazio).
"""
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
OUT = Path(__file__).resolve().parent.parent / "data" / "movielens"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Baixando {URL} ...")
    with urllib.request.urlopen(URL, timeout=120) as resp:
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in ("movies.csv", "ratings.csv"):
            member = f"ml-latest-small/{name}"
            (OUT / name).write_bytes(zf.read(member))
            print(f"  -> {OUT / name}")
    print("Pronto. Os dados do MovieLens são para uso acadêmico; veja o README do GroupLens.")


if __name__ == "__main__":
    main()
