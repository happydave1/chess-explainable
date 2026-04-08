from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Dict

import chess.engine
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.engine_service import analyze_move
from app.schemas import ExplainRequest, ExplainResponse
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


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
