"""API tests; Stockfish required for app lifespan."""

from __future__ import annotations

import shutil
from unittest.mock import AsyncMock, patch

import chess
import pytest
from fastapi.testclient import TestClient

from app.main import app

requires_stockfish = pytest.mark.skipif(
    not shutil.which("stockfish"),
    reason="stockfish not on PATH",
)


@requires_stockfish
def test_health() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@requires_stockfish
def test_illegal_move_400() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/explain",
            json={"fen": chess.Board().fen(), "move": "e2e5"},
        )
    assert r.status_code == 400


@requires_stockfish
def test_explain_mock_slm() -> None:
    stub = "The engine prefers central play; your line matches its evaluation."
    with patch("app.main.explain_with_slm", new_callable=AsyncMock) as m:
        m.return_value = stub
        with TestClient(app) as client:
            r = client.post(
                "/explain",
                json={"fen": chess.Board().fen(), "move": "e2e4"},
            )
    assert r.status_code == 200
    data = r.json()
    assert data["legal"] is True
    assert data["explanation"] == stub
    assert data["engine"]["played_move_san"] == "e4"
    assert data["engine"]["best_move_uci"] == "e2e4"
