from __future__ import annotations

from unittest.mock import patch

import pytest

from app.position import Position
from app.tagger import tag_themes

def _themes(fen: str, move: str) -> list[str]:
    position = Position(fen, move)
    return tag_themes(position)["themes"]


def test_mate_tags_mate_and_mate_in_1() -> None:
    # Scholar's mate final move: Qxf7#
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 4"
    themes = _themes(fen, "h5f7")
    assert "mate" in themes
    assert "mateIn1" in themes


def test_advanced_pawn_tag() -> None:
    themes = _themes("7k/8/4P3/8/8/8/8/K7 w - - 0 1", "e6e7")
    assert "advancedPawn" in themes


def test_double_check_tag() -> None:
    themes = _themes("4k3/8/4N3/8/8/8/8/4R2K w - - 0 1", "e6g7")
    assert "doubleCheck" in themes


def test_quiet_and_defensive_move_tags() -> None:
    themes = _themes("8/8/8/8/8/8/8/4K1Nk w - - 0 1", "g1h3")
    assert "quietMove" in themes
    assert "defensiveMove" in themes


def test_sacrifice_tag() -> None:
    # With single-ply material accounting, this is hard to realize from raw board states;
    # patching material diff isolates the tagging branch itself.
    position = Position("8/8/8/8/8/8/8/4K1Nk w - - 0 1", "g1h3")
    with patch.object(Position, "material_diff", side_effect=[0, -3]):
        themes = tag_themes(position)["themes"]
    assert "sacrifice" in themes


def test_fork_tag() -> None:
    themes = _themes("7k/4r1q1/8/8/3N4/8/8/K7 w - - 0 1", "d4f5")
    assert "fork" in themes


def test_hanging_piece_and_capturing_defender_tags() -> None:
    themes = _themes("7k/3r4/8/8/8/8/8/3Q3K w - - 0 1", "d1d7")
    assert "hangingPiece" in themes
    assert "capturingDefender" in themes


def test_pin_tag() -> None:
    fen = "r3kb1r/pp3ppp/1qn1p3/3pP3/3n2Q1/3BB2P/PP1N1PP1/R4RK1 b kq - 3 13"
    move = "c6e5"
    themes = _themes(fen, move)    
    assert "pin" in themes


def test_attacking_f2_f7_tag() -> None:
    themes = _themes(
        "rnbqkbnr/pppp1ppp/8/4p3/2B5/8/PPPP1PPP/RNBQK1NR w KQkq - 0 1",
        "c4f7",
    )
    assert "attackingF2F7" in themes


def test_en_passant_tag() -> None:
    themes = _themes("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6")
    assert "enPassant" in themes


def test_castling_tag() -> None:
    themes = _themes("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1")
    assert "castling" in themes


def test_promotion_tag() -> None:
    themes = _themes("6k1/4P3/6K1/8/8/8/8/8 w - - 0 1", "e7e8q")
    assert "promotion" in themes
    assert "underPromotion" not in themes


def test_underpromotion_tag() -> None:
    themes = _themes("6k1/4P3/6K1/8/8/8/8/8 w - - 0 1", "e7e8n")
    assert "promotion" in themes
    assert "underPromotion" in themes


@pytest.mark.parametrize(
    ("fen", "move"),
    [
        ("8/8/8/8/8/8/8/4K1Nk w - - 0 1", "g1h3"),
        ("4k3/8/4N3/8/8/8/8/4R2K w - - 0 1", "e6g7"),
        ("6k1/4P3/6K1/8/8/8/8/8 w - - 0 1", "e7e8n"),
    ],
)
def test_themes_payload_shape(fen: str, move: str) -> None:
    payload = tag_themes(Position(fen, move))
    assert isinstance(payload, dict)
    assert "themes" in payload
    assert isinstance(payload["themes"], list)