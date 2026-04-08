from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    fen: str = Field(..., description="FEN of the position before the move")
    move: str = Field(..., description="Move in UCI notation (e.g. e2e4)")


class EngineEvalOut(BaseModel):
    """Stockfish-derived facts; the SLM must not contradict these."""

    depth: int
    best_move_uci: str
    played_move_uci: str
    played_move_san: str
    mover_color: str  # "white" | "black"
    # Scores from the mover's perspective (positive = good for mover); mate > cp when applicable
    score_after_best_cp: Optional[int] = None
    score_after_played_cp: Optional[int] = None
    score_after_best_mate: Optional[int] = None
    score_after_played_mate: Optional[int] = None
    centipawn_loss: Optional[int] = None
    principal_variation_san: list[str] = Field(default_factory=list)


class ExplainResponse(BaseModel):
    legal: bool = True
    engine: Optional[EngineEvalOut] = None
    explanation: str = ""


class ExplainGameRequest(BaseModel):
    pgn: str = Field(..., min_length=1, description="PGN text of a single game (first game is used)")


class GameMoveExplanation(BaseModel):
    """One half-move in the mainline with engine facts and SLM text."""

    ply: int = Field(..., description="Half-move index from the start (1 = White's first move)")
    fen_before: str = Field(..., description="FEN of the position before this move")
    san: str
    uci: str
    engine: EngineEvalOut
    explanation: str


class ExplainGameResponse(BaseModel):
    headers: Dict[str, str] = Field(default_factory=dict, description="PGN tag pairs")
    moves: List[GameMoveExplanation] = Field(default_factory=list)
