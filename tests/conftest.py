"""Fixtures compartilhadas. Os testes usam um SQLite temporário, isolado do banco real."""
import os
import tempfile
from pathlib import Path

# precisa ser definido ANTES de importar a aplicação
_TMP = tempfile.mkdtemp(prefix="recsys-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["SEED_ON_STARTUP"] = "false"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_from_csv  # noqa: E402
from app.services import recommender_service  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


@pytest.fixture
def client():
    """Cliente com banco vazio."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    recommender_service.invalidate()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def seeded_client(client):
    """Cliente com o conjunto de dados de exemplo carregado."""
    with SessionLocal() as db:
        seed_from_csv(db, SAMPLE_DIR)
    recommender_service.invalidate()
    return client


@pytest.fixture
def toy_data():
    """Dados mínimos com dois grupos de gosto bem separados (animação x terror)."""
    items = pd.DataFrame(
        {
            "item_id": [1, 2, 3, 4, 5, 6],
            "title": ["Anim A", "Anim B", "Anim C", "Terror A", "Terror B", "Terror C"],
            "genres": ["Animation|Children", "Animation|Children", "Animation|Comedy", "Horror", "Horror|Thriller", "Horror"],
        }
    )
    ratings = pd.DataFrame(
        [
            # usuários 1 e 2 gostam de animação e odeiam terror
            (1, 1, 5.0), (1, 2, 4.5), (1, 4, 1.0),
            (2, 1, 4.5), (2, 2, 5.0), (2, 3, 5.0), (2, 4, 1.0), (2, 5, 1.5),
            # usuários 3 e 4 gostam de terror
            (3, 4, 5.0), (3, 5, 4.5), (3, 1, 1.0),
            (4, 4, 4.5), (4, 5, 5.0), (4, 6, 5.0), (4, 1, 1.5), (4, 2, 1.0),
        ],
        columns=["user_id", "item_id", "rating"],
    )
    return items, ratings
