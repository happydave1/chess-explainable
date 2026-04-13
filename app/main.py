from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from io import StringIO
from typing import Dict

import chess
import chess.engine
import chess.pgn
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.engine_service import analyze_move
from app.schemas import (
    ExplainGameRequest,
    ExplainGameResponse,
    ExplainRequest,
    ExplainResponse,
    GameMoveExplanation,
)
from app.slm import explain_with_slm


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _transport, engine = await chess.engine.popen_uci(settings.stockfish_path)
    app.state.engine = engine
    try:
        yield
    finally:
        await engine.quit()


app = FastAPI(title="Chess move explanation API", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/")
async def index_page() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index)


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_: Request, exc: RuntimeError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.post("/explain", response_model=ExplainResponse)
async def explain(body: ExplainRequest, request: Request) -> ExplainResponse:
    engine: chess.engine.UciProtocol = request.app.state.engine
    try:
        ev = await analyze_move(engine, body.fen, body.move)
    except HTTPException:
        raise
    text = await explain_with_slm(body.fen, ev, max_words=body.max_words)
    return ExplainResponse(legal=True, engine=ev, explanation=text)


@app.post("/explain-game", response_model=ExplainGameResponse)
async def explain_game(body: ExplainGameRequest, request: Request) -> ExplainGameResponse:
    """Parse a PGN mainline and return an engine-backed SLM explanation for every move."""
    game = chess.pgn.read_game(StringIO(body.pgn))
    if game is None:
        raise HTTPException(status_code=400, detail="Could not parse PGN (empty or invalid)")

    uci_engine: chess.engine.UciProtocol = request.app.state.engine
    headers = dict(game.headers)
    out: list[GameMoveExplanation] = []
    board = game.board()
    ply = 0

    for move in game.mainline_moves():
        ply += 1
        fen_before = board.fen()
        uci = move.uci()
        san = board.san(move)
        try:
            ev = await analyze_move(uci_engine, fen_before, uci)
        except HTTPException:
            raise
        text = await explain_with_slm(fen_before, ev)
        out.append(
            GameMoveExplanation(
                ply=ply,
                fen_before=fen_before,
                san=san,
                uci=uci,
                engine=ev,
                explanation=text,
            )
        )
        board.push(move)

    return ExplainGameResponse(headers=headers, moves=out)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
