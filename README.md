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

# 4. Voice (optional) — paste SARVAM_API_KEY from dashboard.sarvam.ai into .env
#    Leave it blank and the app runs exactly as before, minus the mic/speaker.

# 5. Frontend deps
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
python -m pytest tests/ -q        # 67 unit tests, no API key needed
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

**NVIDIA NIM is the single external dependency for reasoning** — chat, vision OCR
and embeddings all run through it, so there is one key and one failure domain.

**Voice is a second, optional domain.** No model this NVIDIA key reaches does
speech (only `riva-translate`, which is text), and Riva's TTS voices skip Tamil
regardless — so speech-to-text, text-to-speech and transliteration go to Sarvam
AI. It is isolated by design: its own provider, its own counters, and a blank
`SARVAM_API_KEY` simply hides the voice UI instead of breaking anything.

### Design decisions worth knowing

| Decision | Why |
|---|---|
| **numpy, not FAISS/Chroma** | One textbook is a few hundred chunks; exact cosine is sub-millisecond there. FAISS solves a scale problem we don't have; Chroma adds a server to babysit on stage. Swappable behind `VectorStore`. |
| **Refusal decided on retrieval scores, not by the LLM** | A prompt-only guardrail can be argued out of refusing. This one is deterministic, instant, and spends zero generation calls — provable live via `/api/stats`. |
| **No `json_schema` response format** | Support varies per NIM model. We use a tolerant parser + one repair retry + Pydantic defaults, then degrade gracefully rather than erroring at a judge. |
| **Three system prompts, not one** | Teaching, grading and question-writing have different objectives and output contracts. |
| **Language rules, not example sentences** | Hardcoded examples get parroted verbatim. Register rules generalise. Bit us for real once already: the OCR prompt's `e.g. [Diagram: cross-section of a leaf]` line made the vision model return exactly that string as the entire transcription of an unrelated page. |
| **A model's chat capability is not its vision capability** | `chat()`'s backup-model retry is disabled for OCR (`allow_backup=False`). The configured text backup can't accept images, so a failed vision call was retrying on a model guaranteed to reject it — and that rejection ("multimodal processing is not enabled") was overwriting the real error. |
| **Short answers are never auto-graded** | Keyword matching would mark correct Tanglish wrong — precisely the failure this product exists to prevent. |
| **SQLite, no auth** | Auth earns zero rubric points and costs demo time. |
| **Tanglish is transliterated before it is spoken** | Tanglish is Tamil in Latin script. An English voice mangles the words; a Tamil voice can't read the letters. So the text is converted to Tamil script for the audio only — the screen still shows Latin. |
| **Speech-to-text uses Sarvam's `translit` mode** | A student speaks Tamil and the textarea fills with romanised text — the exact format every other layer already expects, with no conversion step on the way in. |
| **Voice calls counted separately from NIM calls** | `nim_calls` has to keep meaning "LLM calls", or the refusal-spends-nothing proof in judge mode stops proving anything. |
| **Recordings re-encoded to 16 kHz mono WAV in the browser** | Sarvam's docs list WebM as accepted; the live API rejects it, and WebM/Opus is the only thing Chrome's `MediaRecorder` produces. The Web Audio API converts it client-side — no ffmpeg on the server, and a ~6x smaller upload since speech gains nothing from stereo at 48 kHz. |
| **Vision model dispatched by name, not one fixed request shape** | A "parse" family model (`nemotron-parse`) takes no text prompt at all, selects transcription mode via a `tools` field, and returns a tool call instead of message content — nothing like a general vision-chat model. `_is_parse_model()` in `provider.py` routes to the matching request builder. |
| **LaTeX tables flattened before indexing** | `nemotron-parse` renders every detected table as raw LaTeX (`\begin{tabular}...`). Left alone, that markup pollutes RAG chunks and gets read aloud verbatim by TTS; `flatten_latex_tables()` turns each row into a plain line. |
| **OCR cache keyed on the vision model, not just image bytes** | Switching `NVIDIA_MODEL_VISION` must invalidate cached transcriptions — otherwise a page OCR'd by a since-replaced (or since-fixed) model keeps being served from disk forever, silently. |

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
