"""OpenAI-compatible chat completions for local SLM (e.g. Ollama)."""

from __future__ import annotations

import json
from typing import Any, Dict

import httpx

from app.config import settings
from app.schemas import EngineEvalOut


SYSTEM_PROMPT = """You explain chess like a human coach: say why the played move is good, bad, or roughly equal for the position.

You must stay faithful to the facts in the analysis block you are given (who stands better after each choice, how big the gap is, mate if present)—but your answer must sound like normal chess talk, not a report about software.

Never use these words or close variants: engine, Stockfish, computer, evaluation, centipawn, centipawns, CP, node, depth, analysis (as in “the analysis says”), database. Do not say “according to” or “the numbers show.”

Use ordinary chess ideas: initiative, threats, king safety, piece activity, structure, tactics, tempo, material. Do not invent moves that are not reflected in the supplied line preview.

One short phrase or sentence. Plain English. No bullet points or line breaks."""


def _analysis_payload_for_prompt(engine: EngineEvalOut) -> Dict[str, Any]:
    """Facts for the model; labels avoid engine jargon so the reply stays human-sounding."""
    return {
        "mover": engine.mover_color,
        "played_move_san": engine.played_move_san,
        "stronger_alternative_first_move_san": engine.principal_variation_san[0]
        if engine.principal_variation_san
        else None,
        "main_line_preview_san": engine.principal_variation_san[:8],
        "position_after_played_vs_after_alternative": {
            "advantage_for_mover_after_alternative": engine.score_after_best_cp,
            "advantage_for_mover_after_played": engine.score_after_played_cp,
            "how_much_weaker_played_is_than_alternative": engine.centipawn_loss,
            "mate_threat_after_alternative": engine.score_after_best_mate,
            "mate_threat_after_played": engine.score_after_played_mate,
        },
    }


def build_user_message(fen: str, engine: EngineEvalOut) -> str:
    facts = _analysis_payload_for_prompt(engine)
    return (
        "Position before the move (FEN):\n"
        f"{fen}\n\n"
        "Facts you must respect (do not mention this block or its labels in your answer):\n"
        f"{json.dumps(facts, indent=2)}\n\n"
        "Explain why the played move is good or bad compared to leading with the alternative "
        "first move and the line preview—without referring to how you know."
    )


async def explain_with_slm(fen: str, engine: EngineEvalOut) -> str:
    base = settings.slm_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if settings.slm_api_key:
        headers["Authorization"] = f"Bearer {settings.slm_api_key}"

    body = {
        "model": settings.slm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(fen, engine)},
        ],
        "stream": False,
        "max_tokens": settings.slm_max_tokens,
    }

    async with httpx.AsyncClient(timeout=settings.slm_timeout_s) as client:
        try:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            body_txt = e.response.text[:500] if e.response is not None else ""
            raise RuntimeError(f"SLM HTTP {e.response.status_code}: {body_txt}") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"SLM request failed: {e}") from e
        data = r.json()

    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected SLM response shape: {data!r}") from e
