# Chess explainable (MVP)

FastAPI service that accepts a FEN and a UCI move, runs **Stockfish** to score the best line versus the played line, then asks a **small language model** (OpenAI-compatible API, e.g. **Ollama**) to explain those engine facts in natural language. The model does not judge the position itself; only the engine numbers are authoritative.

## Prerequisites

- Python 3.9+
- [Stockfish](https://stockfishchess.org/) on your `PATH` or set `STOCKFISH_PATH`
- A running SLM with an OpenAI-compatible HTTP API (this repo defaults to [Ollama](https://ollama.com/))

### Install Stockfish

- macOS: `brew install stockfish`
- Ubuntu: `sudo apt install stockfish`

### Run an SLM with Ollama

Install Ollama, then pull a small model and keep the server running:

```bash
ollama pull llama3.2
ollama serve
```

Match `SLM_MODEL` in `.env` to the model name you pulled (e.g. `llama3.2`).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edit .env if Stockfish or Ollama are not at the defaults
```

## Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET http://localhost:8000/health`
- Explain: `POST http://localhost:8000/explain`

### Example request

```bash
curl -s -X POST http://localhost:8000/explain \
  -H "Content-Type: application/json" \
  -d '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","move":"e2e4"}' | jq .
```

The response includes `engine` (Stockfish-derived fields, including optional `centipawn_loss`) and `explanation` (text from the SLM).

## Configuration

Environment variables are loaded from `.env` (see [.env.example](.env.example)). Names map to `STOCKFISH_PATH`, `ENGINE_DEPTH`, `ENGINE_TIME_LIMIT_S`, `SLM_BASE_URL`, `SLM_MODEL`, `SLM_API_KEY`, `SLM_TIMEOUT_S`, `SLM_MAX_TOKENS` (API `max_tokens`).

## Development tests

```bash
pip install -e ".[dev]"
pytest
```

Integration tests run only when Stockfish is available.
