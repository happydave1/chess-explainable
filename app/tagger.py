from __future__ import annotations

from typing import Any

import chess

from app.position import Position


def _mate_tag(position: Position) -> str | None:
    if not position.is_checkmate():
        return None
    # With current API input this is always a single played move.
    return "mateIn1"


def _advanced_pawn(position: Position) -> bool:
    if position.moved_piece_type != chess.PAWN:
        return False
    rank = chess.square_rank(position.move.to_square)
    return rank >= 5 if position.pov == chess.WHITE else rank <= 2


def _quiet_move(position: Position) -> bool:
    if position.is_capture() or position.gives_check():
        return False
    if position.moved_piece_type in (None, chess.KING, chess.PAWN):
        return False
    attacked = position.board_after.attacks(position.move.to_square)
    return not any(
        (piece := position.board_after.piece_at(sq)) is not None and piece.color != position.pov
        for sq in attacked
    )


def _defensive_move(position: Position) -> bool:
    if position.board_before.legal_moves.count() < 3:
        return False
    if position.is_capture() or position.gives_check():
        return False
    return not _advanced_pawn(position)


def _sacrifice(position: Position) -> bool:
    if position.is_promotion():
        return False
    before = position.material_diff(position.board_before)
    after = position.material_diff(position.board_after)
    return after - before <= -2


def _fork(position: Position) -> bool:
    moved = position.moved_piece_type
    if moved in (None, chess.KING, chess.PAWN):
        return False
    to_sq = position.move.to_square
    # Avoid "fork" for obviously loose attackers.
    if position.is_hanging(position.board_after, to_sq):
        return False
    threatened = 0
    for sq in position.board_after.attacks(to_sq):
        target = position.board_after.piece_at(sq)
        if target is None or target.color == position.pov or target.piece_type == chess.PAWN:
            continue
        target_value = position.value(target.piece_type)
        if target_value > position.value(moved) or position.is_hanging(position.board_after, sq):
            threatened += 1
    return threatened > 1


def _hanging_piece(position: Position) -> bool:
    captured = position.captured_piece
    if captured is None or captured.piece_type == chess.PAWN:
        return False
    return position.is_hanging(position.board_before, position.move.to_square)


def _pin(position: Position) -> bool:
    for sq, piece in position.board_after.piece_map().items():
        if piece.color == position.pov:
            continue
        if position.board_after.is_pinned(piece.color, sq):
            return True
    return False


def _attacking_f2_f7(position: Position) -> bool:
    if not position.is_capture() or position.move.to_square not in (chess.F2, chess.F7):
        return False
    enemy_king = position.board_after.piece_at(chess.E8 if position.move.to_square == chess.F7 else chess.E1)
    return (
        enemy_king is not None
        and enemy_king.piece_type == chess.KING
        and enemy_king.color != position.pov
    )


def _capturing_defender(position: Position) -> bool:
    if not position.is_capture():
        return False
    captured = position.captured_piece
    moved = position.moved_piece_type
    if captured is None or moved is None or moved == chess.KING:
        return False
    if position.value(captured.piece_type) > position.value(moved):
        return False
    return position.is_hanging(position.board_before, position.move.to_square)


def tag_themes(position: Position) -> dict[str, Any]:
    """
    Lichess-inspired move theme tagger adapted for single-move position analysis.
    """
    tags: list[str] = []

    mate = _mate_tag(position)
    if mate:
        tags.append(mate)
        tags.append("mate")

    if _advanced_pawn(position):
        tags.append("advancedPawn")
    if position.is_double_check():
        tags.append("doubleCheck")
    if _quiet_move(position):
        tags.append("quietMove")
    if _defensive_move(position):
        tags.append("defensiveMove")
    if _sacrifice(position):
        tags.append("sacrifice")
    if _fork(position):
        tags.append("fork")
    if _hanging_piece(position):
        tags.append("hangingPiece")
    if _pin(position):
        tags.append("pin")
    if _attacking_f2_f7(position):
        tags.append("attackingF2F7")
    if position.is_en_passant():
        tags.append("enPassant")
    if position.is_castling():
        tags.append("castling")
    if position.is_promotion():
        tags.append("promotion")
    if position.is_underpromotion():
        tags.append("underPromotion")
    if _capturing_defender(position):
        tags.append("capturingDefender")
    return {"themes": tags}