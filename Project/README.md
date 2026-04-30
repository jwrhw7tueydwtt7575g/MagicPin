# MagicPin AI Challenge Bot

Stateful FastAPI bot for the magicpin AI challenge with:
- full runtime API (`/v1/context`, `/v1/tick`, `/v1/reply`, `/v1/healthz`, `/v1/metadata`)
- optional `/v1/teardown` support
- deterministic composition pipeline (Groq Llama 3.1 70B Versatile + guarded rule-based fallback)
- offline `submission.jsonl` generator from canonical 30 test pairs

## Project Structure

- `Project/app.py` - FastAPI entrypoint and endpoint orchestration.
- `Project/config.py` - env/config loader (`.env` support).
- `Project/core/` - composer, prompts, CTA/send_as rules, language strategy.
- `Project/llm/groq_client.py` - Groq API integration with fail-safe fallback behavior.
- `Project/runtime/` - trigger selection and reply engine logic.
- `Project/store/` - in-memory state, context versioning, conversation store.
- `Project/offline/generate_submission.py` - canonical offline output generator.
- `Project/tests/` - unit and integration tests.
- `bot.py` - top-level `compose(...)` helper contract.

## Requirements

- Python 3.12+
- Internet access for Groq API calls
- Optional: public URL/tunnel (`ngrok`, cloud host) for remote judging

## Environment Configuration

Create a root `.env` file (or use `Project/.env`) and set:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-70b-versatile
REQUEST_TIMEOUT_SECONDS=20
MAX_ACTIONS_PER_TICK=20
TEAM_NAME=MagicPin Team
TEAM_MEMBERS=Vivek
CONTACT_EMAIL=team@example.com
APP_VERSION=0.1.0
```

Notes:
- If `GROQ_API_KEY` is missing/invalid, the bot still runs using deterministic rule-based fallback.
- Never commit `.env` or real API keys.

## Setup

From repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r Project/requirements.txt
```

## Run the API

```bash
uvicorn Project.app:app --host 0.0.0.0 --port 8080
```

Local base URL: `http://localhost:8080`

## Required Endpoints

- `POST /v1/context` - ingest versioned context (`category|merchant|customer|trigger`).
- `POST /v1/tick` - proactive action generation from active triggers.
- `POST /v1/reply` - synchronous conversation continuation (`send|wait|end`).
- `GET /v1/healthz` - liveness + context counts.
- `GET /v1/metadata` - bot identity metadata.
- `POST /v1/teardown` - optional state reset after run.

## Quick Contract Smoke Test

```bash
curl -s http://localhost:8080/v1/healthz
curl -s http://localhost:8080/v1/metadata
```

## Run Tests

```bash
pytest -q Project/tests
```

## End-to-End Local Validation

Recommended flow:
1. Start API server.
2. Push contexts (`/v1/context`) from expanded dataset.
3. Call `/v1/tick` with active trigger IDs.
4. Call `/v1/reply` for multi-turn scenarios.
5. Call `/v1/teardown` and re-check `/v1/healthz`.

The repository includes scenario-ready data under `Information/dataset/expanded`.

## Generate Offline Submission

1) Build expanded canonical dataset (if missing):

```bash
python3 Information/dataset/generate_dataset.py --seed-dir Information/dataset --out Information/dataset/expanded
```

2) Generate root `submission.jsonl`:

```bash
python3 -m Project.offline.generate_submission
```

Expected output:
- file at repository root: `submission.jsonl`
- exactly 30 lines
- each line includes:
  - `test_id`
  - `body`
  - `cta`
  - `send_as`
  - `suppression_key`
  - `rationale`

## Deployment Notes

- Deploy `Project.app:app` as the HTTP bot service.
- Ensure public base URL exposes:
  - `POST /v1/context`
  - `POST /v1/tick`
  - `POST /v1/reply`
  - `GET /v1/healthz`
  - `GET /v1/metadata`
- Keep server warm and avoid restarts during judge window (state is in-memory).

## Troubleshooting

- `groq_api_key_present: false`:
  - Verify root `.env` has `GROQ_API_KEY=...`
  - Restart server after updating `.env`
- Groq request errors:
  - client retries with a compatibility payload
  - if still failing, composer returns deterministic fallback content
- Port already in use:
  - stop previous process or run with a different port.
