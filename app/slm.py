"""OpenAI-compatible chat completions for local SLM (e.g. Ollama)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict

import httpx

from app.config import settings
from app.schemas import EngineEvalOut


SYSTEM_PROMPT = """You explain chess like a human coach for beginners: say why the played move is good, bad, or roughly equal for the position.

You must stay faithful to the facts in the analysis block you are given (who stands better after each choice, how big the gap is, mate if present)—but your answer must sound like normal chess talk, not a report about software.

Never use these words or close variants: engine, Stockfish, computer, evaluation, centipawn, centipawns, CP, node, depth, analysis (as in “the analysis says”), database. Do not say “according to” or “the numbers show.”

Use very simple words and short sentences. Assume the reader is new to chess. Explain with one clear idea only (for example: king safety, hanging piece, faster development, or a direct threat). If you use a chess term, keep it basic and common.

Do not invent moves that are not reflected in the supplied line preview.

One short sentence in plain English, ideally 8-16 words. No bullet points or line breaks."""

DANGLING_END_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "because",
    "but",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "it",
    "of",
    "on",
    "or",
    "so",
    "than",
    "that",
    "the",
    "then",
    "this",
    "to",
    "when",
    "while",
    "which",
    "with",
    "without",
    "making",
    "preparing",
    "leading",
    "lead",
    "giving",
    "give",
    "taking",
    "take",
    "keeping",
    "keep",
    "put",
    "puts",
    "open",
    "opens",
    "creating",
}


def _build_system_prompt(max_words: int | None = None) -> str:
    if max_words is None:
        return SYSTEM_PROMPT
    return f"{SYSTEM_PROMPT}\n\nHard limit: use at most {max_words} words."


def _truncate_to_words(text: str, max_words: int | None = None) -> str:
    cleaned = text.strip()
    if not cleaned or max_words is None:
        return cleaned

    # Prefer a complete first sentence to avoid cutting thoughts mid-way.
    sentence_match = re.match(r"^(.+?[.!?])(?:\s|$)", cleaned)
    if sentence_match:
        first_sentence = sentence_match.group(1).strip()
        if len(first_sentence.split()) <= max_words:
            return first_sentence

    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned if cleaned[-1] in ".!?" else f"{cleaned.rstrip(' ,;:-')}."

    clipped_words = words[:max_words]
    while (
        len(clipped_words) > 4
        and clipped_words[-1].rstrip(".,!?;:").lower() in DANGLING_END_WORDS
    ):
        clipped_words.pop()

    clipped = " ".join(clipped_words).rstrip(" ,;:-")
    return clipped if clipped.endswith((".", "!", "?")) else f"{clipped}."


def _looks_complete_sentence(text: str, max_words: int | None = None) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    if max_words is not None and len(cleaned.split()) > max_words:
        return False
    if cleaned[-1] not in ".!?":
        return False
    last_word = re.sub(r"[^\w'-]", "", cleaned.split()[-1]).lower()
    if not last_word:
        return False
    if "," in cleaned or ";" in cleaned or ":" in cleaned:
        return False
    if last_word.endswith("ing"):
        return False
    if last_word in {"slightly", "somewhat", "more", "less"}:
        return False
    return last_word not in DANGLING_END_WORDS


def _fallback_explanation(engine: EngineEvalOut, max_words: int | None = None) -> str:
    cpl = engine.centipawn_loss
    if cpl is None:
        text = f"{engine.played_move_san} is playable and keeps the game balanced."
    elif cpl <= 20:
        text = f"{engine.played_move_san} is solid and keeps the position about equal."
    elif cpl <= 80:
        text = f"{engine.played_move_san} is okay, but a stronger move keeps more pressure."
    else:
        text = f"{engine.played_move_san} is a big inaccuracy and gives up too much."
    return _truncate_to_words(text, max_words=max_words)


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


async def explain_with_slm(fen: str, engine: EngineEvalOut, max_words: int | None = None) -> str:
    if max_words is not None:
        # Deterministic path for strict brevity: always complete and within limit.
        return _fallback_explanation(engine, max_words=max_words)

    base = settings.slm_base_url.rstrip("/")
    url = f"{base}/chat/completions"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if settings.slm_api_key:
        headers["Authorization"] = f"Bearer {settings.slm_api_key}"

    user_prompt = build_user_message(fen, engine)
    last_text = ""
    async with httpx.AsyncClient(timeout=settings.slm_timeout_s) as client:
        for _ in range(2):
            body = {
                "model": settings.slm_model,
                "messages": [
                    {"role": "system", "content": _build_system_prompt(max_words=max_words)},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "max_tokens": settings.slm_max_tokens,
            }
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
                content = (data["choices"][0]["message"]["content"] or "").strip()
            except (KeyError, IndexError, TypeError) as e:
                raise RuntimeError(f"Unexpected SLM response shape: {data!r}") from e

            last_text = _truncate_to_words(content, max_words=max_words)
            if _looks_complete_sentence(last_text, max_words=max_words):
                return last_text

            user_prompt = (
                f"{build_user_message(fen, engine)}\n\n"
                "Rewrite as one complete sentence only. Do not leave a dangling ending."
            )

    if _looks_complete_sentence(last_text, max_words=max_words):
        return last_text
    return _fallback_explanation(engine, max_words=max_words)
