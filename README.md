# Bodhi — AI Textbook Tutor in Your Mother Tongue

**PS-S01.** Upload a textbook page. Bodhi teaches it back in natural
Tamil/Tanglish, grounded strictly in your upload, then runs
*teach back → misconception detection → correction → adaptive practice*.

---

## Setup

```bash
# 1. Backend deps (conda env `bodhi`, Python 3.11)
/opt/anaconda3/envs/bodhi/bin/pip install -r requirements.txt

# 2. Configure the one secret
cp .env.example .env
#    → paste your NVIDIA_API_KEY from build.nvidia.com

# 3. Pick the model with evidence, not guesswork
python -m scripts.benchmark_nim --list          # what your key can reach
python -m scripts.benchmark_nim                 # score the top candidates
#    → copy the printed NVIDIA_MODEL / NVIDIA_MODEL_BACKUP lines into .env

# 4. Frontend deps
cd frontend && npm install
```

## Run

```bash
# terminal 1
/opt/anaconda3/envs/bodhi/bin/python -m uvicorn backend.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev        # http://localhost:5173
```

## Verify

```bash
python -m pytest tests/ -q        # 49 unit tests, no API key needed
python -m scripts.demo_check      # full judge sequence against a live backend
```

---

## Architecture

```
React + Vite + Tailwind (single page, step rail)
        │  /api  — the browser never sees the NIM key
        ▼
     FastAPI
        │
 ┌──────┼──────────────┬────────────┐
 ▼      ▼              ▼            ▼
Ingest  RAG        LLMService     SQLite
 │       │              │
PyMuPDF  embed +     NIM provider
 + VLM   numpy       ├ tutor
  OCR    cosine      ├ evaluator
         + grounding └ practice
          threshold      │
              NVIDIA NIM /v1/chat/completions
```

**NVIDIA NIM is the single external dependency** — chat, vision OCR and
embeddings all run through it, so there is one key and one failure domain.

### Design decisions worth knowing

| Decision | Why |
|---|---|
| **numpy, not FAISS/Chroma** | One textbook is a few hundred chunks; exact cosine is sub-millisecond there. FAISS solves a scale problem we don't have; Chroma adds a server to babysit on stage. Swappable behind `VectorStore`. |
| **Refusal decided on retrieval scores, not by the LLM** | A prompt-only guardrail can be argued out of refusing. This one is deterministic, instant, and spends zero generation calls — provable live via `/api/stats`. |
| **No `json_schema` response format** | Support varies per NIM model. We use a tolerant parser + one repair retry + Pydantic defaults, then degrade gracefully rather than erroring at a judge. |
| **Three system prompts, not one** | Teaching, grading and question-writing have different objectives and output contracts. |
| **Language rules, not example sentences** | Hardcoded examples get parroted verbatim. Register rules generalise. |
| **Short answers are never auto-graded** | Keyword matching would mark correct Tanglish wrong — precisely the failure this product exists to prevent. |
| **SQLite, no auth** | Auth earns zero rubric points and costs demo time. |

### Asymmetric embeddings — the easiest thing to get wrong

NeMo Retriever models embed questions and passages differently. Using the wrong
side produces **no error**, just quietly worse retrieval. Hence
`embed_query()` and `embed_passages()` are separate functions rather than one
function with a flag.

---

## The demo sequence

1. Upload `demo/photosynthesis.txt` (or a photo/PDF of a page)
2. Ask **"Photosynthesis-na enna?"** → grounded Tanglish explanation
3. Grounding card shows the page number and verbatim source
4. Ask **"Who is the current Prime Minister of India?"** → refused, **no LLM call spent**
5. Teach back *"Plant sunlight ah use panni food make pannum"* → graded **correct** despite informal Tanglish
6. Teach back *"Plants oda food is soil"* → the **specific** misconception is named and corrected
7. Generate practice → 5 MCQs + 2 short answers
8. Answer wrong → difficulty visibly drops, with the reason stated

**Judge mode** (left rail) exposes retrieval scores, the threshold decision, and
live NIM call counts.

## Layout

```
backend/
  config.py         settings + per-task model overrides
  main.py           FastAPI routes
  db.py             SQLite — 5 tables
  adaptive.py       transparent rule-based difficulty
  cache.py          content-hashed OCR/embedding cache
  llm/              provider · service · prompts · json_utils
  ingest/           extract · clean · chunk
  rag/              embeddings · store · retrieve
frontend/src/       App.jsx · steps/ · components/
scripts/            benchmark_nim.py · demo_check.py
tests/              test_core.py
demo/               photosynthesis.txt
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `health` shows `degraded` | `NVIDIA_API_KEY` missing from `.env` |
| `No NVIDIA_MODEL configured` | Run `scripts/benchmark_nim.py`, paste the result into `.env` |
| Everything refused as out-of-scope | Lower `GROUNDING_THRESHOLD` in `.env` |
| Nothing refused | Raise `GROUNDING_THRESHOLD` |
| `Query dim != index dim` | Embedding model changed — delete `data/index/` and re-upload |
| Model returns bad JSON | Set `NVIDIA_MODEL_STRUCTURED` to a JSON-reliable model |
