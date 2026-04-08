"""
Stockfish analysis for move explanation.

Centipawn loss metric (documented for SLM prompts):
- From the parent position, the player to move is the "mover".
- We compare the value of the resulting position after the engine's best move vs after the
  played move, both evaluated from the *mover's* perspective (positive = good for the mover).
- cp_loss = score_after_best - score_after_played, using centipawns only when both results
  are non-mate scores. If either side is a mate score, centipawn_loss is null and mate fields apply.
"""

from __future__ import annotations

from typing import Optional, Tuple

import chess
import chess.engine
from fastapi import HTTPException

from app.config import settings
from app.schemas import EngineEvalOut


def _limit() -> chess.engine.Limit:
    if settings.engine_time_limit_s is not None:
        return chess.engine.Limit(time=settings.engine_time_limit_s)
    return chess.engine.Limit(depth=settings.engine_depth)


def _score_tuple(s: chess.engine.Score) -> Tuple[str, Optional[int]]:
    if s.is_mate():
        return ("mate", s.mate())
    return ("cp", s.score())


def _pv_to_san(board: chess.Board, pv: list[chess.Move], max_plies: int = 8) -> list[str]:
    out: list[str] = []
    b = board.copy()
    for m in pv[:max_plies]:
        if m not in b.legal_moves:
            break
        out.append(b.san(m))
        b.push(m)
    return out


async def analyze_move(
    engine: chess.engine.UciProtocol,
    fen: str,
    uci_move: str,
) -> EngineEvalOut:
    try:
        board = chess.Board(fen)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {e}") from e

    mover = board.turn
    mover_color = "white" if mover == chess.WHITE else "black"

    try:
        move = chess.Move.from_uci(uci_move.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UCI move: {e}") from e

    # `legal_moves` iterates `chess.Move` objects (UCI is only how we parse input); use is_legal.
    if not board.is_legal(move):
        raise HTTPException(status_code=400, detail="Illegal move for this position")

    limit = _limit()

    root_info = await engine.analyse(board, limit)
    depth = root_info.get("depth", settings.engine_depth)
    pv_root = root_info.get("pv", [])
    if not pv_root:
        raise HTTPException(status_code=500, detail="Engine returned no principal variation")

    best_move = pv_root[0]
    best_move_uci = best_move.uci()

    board_after_played = board.copy()
    board_after_played.push(move)

    if best_move == move:
        info_best = await engine.analyse(board_after_played, limit)
        info_played = info_best
    else:
        board_after_best = board.copy()
        board_after_best.push(best_move)
        info_best = await engine.analyse(board_after_best, limit)
        info_played = await engine.analyse(board_after_played, limit)

    sb = info_best["score"].pov(mover)
    su = info_played["score"].pov(mover)
    kind_b, val_b = _score_tuple(sb)
    kind_u, val_u = _score_tuple(su)

    score_after_best_cp: Optional[int] = val_b if kind_b == "cp" else None
    score_after_played_cp: Optional[int] = val_u if kind_u == "cp" else None
    score_after_best_mate: Optional[int] = val_b if kind_b == "mate" else None
    score_after_played_mate: Optional[int] = val_u if kind_u == "mate" else None

    centipawn_loss: Optional[int] = None
    if kind_b == "cp" and kind_u == "cp" and val_b is not None and val_u is not None:
        centipawn_loss = val_b - val_u

    pv_san = _pv_to_san(board, pv_root)

    return EngineEvalOut(
        depth=depth,
        best_move_uci=best_move_uci,
        played_move_uci=move.uci(),
        played_move_san=board.san(move),
        mover_color=mover_color,
        score_after_best_cp=score_after_best_cp,
        score_after_played_cp=score_after_played_cp,
        score_after_best_mate=score_after_best_mate,
        score_after_played_mate=score_after_played_mate,
        centipawn_loss=centipawn_loss,
        principal_variation_san=pv_san,
    )
