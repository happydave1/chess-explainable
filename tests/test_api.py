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


def post_explain_game_explanations_only(client: TestClient, pgn: str) -> list[str]:
    """POST /explain-game with `pgn` and return only the explanation strings, in move order."""
    r = client.post("/explain-game", json={"pgn": pgn})
    r.raise_for_status()
    return [row["explanation"] for row in r.json()["moves"]]


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


@requires_stockfish
def test_explain_game_mock_slm() -> None:
    stub = "Short explanation."
    pgn = '[Event "Test"]\n\n1. e4 e5 2. Nf3 Nc6 *\n'
    with patch("app.main.explain_with_slm", new_callable=AsyncMock) as m:
        m.return_value = stub
        with TestClient(app) as client:
            r = client.post("/explain-game", json={"pgn": pgn})
    assert r.status_code == 200
    data = r.json()
    assert data["headers"].get("Event") == "Test"
    assert len(data["moves"]) == 4
    for i, row in enumerate(data["moves"], start=1):
        assert row["ply"] == i
        assert row["explanation"] == stub
        assert "engine" in row
    assert data["moves"][0]["san"] == "e4"
    assert data["moves"][1]["san"] == "e5"
    assert data["moves"][2]["san"] == "Nf3"
    assert data["moves"][3]["san"] == "Nc6"


@requires_stockfish
def test_explain_game_invalid_pgn_400() -> None:
    with TestClient(app) as client:
        r = client.post("/explain-game", json={"pgn": "   "})
    assert r.status_code == 400
    assert "parse" in r.json()["detail"].lower()


@requires_stockfish
def test_post_explain_game_explanations_only() -> None:
    stub = "Only this text matters."
    pgn = '[Event "Mini"]\n\n1. e4 e5 *\n'
    with patch("app.main.explain_with_slm", new_callable=AsyncMock) as m:
        m.return_value = stub
        with TestClient(app) as client:
            explanations = post_explain_game_explanations_only(client, pgn)
    assert explanations == [stub, stub]
