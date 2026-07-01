# CopilotKit + LangGraph Subgraphs — Travel Planner

> **Stack**: Vite + React 19 + TypeScript frontend served as static files from a FastAPI backend.
> No Node.js server in production — one `python main.py` runs everything.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI (port 8123)                      │
│                                                              │
│  /api/copilotkit  ← CopilotKit Python SDK  (LangGraph graph) │
│  /assets/*        ← Vite build output (JS/CSS)               │
│  /*               ← SPA fallback (index.html)                │
└──────────────────────────────────────────────────────────────┘
        ▲
        │  dev: Vite proxy  /api → http://localhost:8123
        │  prod: same origin (no proxy needed)
┌──────────────────────────────────────────────────────────────┐
│            Vite dev server (port 5173) — dev only             │
└──────────────────────────────────────────────────────────────┘
```

### LangGraph subgraphs

```
Supervisor
  ├── FlightsSubgraph   (searches / generates flight options)
  ├── HotelsSubgraph    (searches / generates hotel options)
  └── ExperiencesSubgraph (searches / generates local experiences)
        └── Coordinator  (summarises all results)
```

## Quick start

### 1. Backend

```bash
cd agent
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

copy .env.example .env        # add OPENAI_API_KEY
python main.py                # starts on http://localhost:8123
```

### 2. Frontend (development)

```bash
cd ui
npm install
npm run dev                   # Vite dev server on http://localhost:5173
```

Open <http://localhost:5173>.

### 3. Production (static files served by FastAPI)

```bash
cd ui
npm run build                 # outputs ui/dist/

cd ../agent
python main.py                # serves everything on http://localhost:8123
```

Open <http://localhost:8123>.

A full-stack AI travel planning app that demonstrates **LangGraph subgraphs** with **CopilotKit** and a **Python FastAPI** backend.

Reference demo: [dojo.ag-ui.com/langgraph-fastapi/feature/subgraphs](https://dojo.ag-ui.com/langgraph-fastapi/feature/subgraphs)

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Next.js Frontend (React)                                │
│                                                          │
│  CopilotKit Provider ──► /api/copilotkit (Next.js route) │
│         │                        │                       │
│  useAgent() hook          LangGraphAgent                 │
│  reads agent.state        points to FastAPI              │
│  (flights/hotels/etc)                                    │
└──────────────────────┬───────────────────────────────────┘
                       │ AG-UI protocol (HTTP streaming)
┌──────────────────────▼───────────────────────────────────┐
│  Python FastAPI + ag_ui_langgraph                        │
│                                                          │
│  Supervisor graph                                        │
│    ├── flights_subgraph    ← nested StateGraph           │
│    ├── hotels_subgraph     ← nested StateGraph           │
│    └── experiences_subgraph ← nested StateGraph          │
│                                                          │
│  State streams to frontend automatically                 │
└──────────────────────────────────────────────────────────┘
```

### Agent flow

1. **Supervisor node** — LLM parses user intent, sets routing flags (`needs_flights`, `needs_hotels`, `needs_experiences`) and extracts origin/destination.
2. **Flights subgraph** — Generates realistic flight options, updates `state.flights`.
3. **Hotels subgraph** — Generates hotel options, updates `state.hotels`.
4. **Experiences subgraph** — Plans experiences/activities, updates `state.experiences`.
5. **Coordinator node** — Generates a final summary message once all required subgraphs have run.

State from every subgraph streams to the React frontend in real-time via the AG-UI protocol — no extra agent-side wiring needed.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Node.js | 18+ |
| Python | 3.10+ |
| pip / venv | latest |
| OpenAI API key | — |

---

## Quick Start

### 1 — Clone / open the project

```bash
cd copilotkit_demo
```

### 2 — Set up the Python backend

```bash
cd agent

# Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure your OpenAI key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start the FastAPI server (port 8123)
python main.py
```

The API is now running at `http://localhost:8123`.  
Health check: `curl http://localhost:8123/health`

### 3 — Set up the Next.js frontend

Open a **new terminal**:

```bash
cd ui

# Install dependencies
npm install           # or: pnpm install / yarn install / bun install

# Configure environment
cp .env.local.example .env.local
# AGENT_URL defaults to http://localhost:8123 — no change needed for local dev

# Start the dev server
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## Usage

Type in the chat panel (right side):

| Prompt | What happens |
|--------|-------------|
| `Plan a trip from Amsterdam to San Francisco` | All three subgraphs run — flights + hotels + experiences appear in the itinerary |
| `Find me flights from New York to Tokyo` | Only the flights subgraph runs |
| `What hotels are available in Paris?` | Only the hotels subgraph runs |
| `What can I do in Barcelona?` | Only the experiences subgraph runs |

Watch the **Active Agent** badges in the top-right of the itinerary panel update in real time as each subgraph executes.

---

## Project Structure

```
copilotkit_demo/
├── agent/                    Python FastAPI backend
│   ├── agent.py              Supervisor + subgraphs (LangGraph)
│   ├── main.py               FastAPI server entry-point
│   ├── requirements.txt
│   └── .env.example
│
└── ui/                       Next.js frontend
    ├── src/
    │   ├── app/
    │   │   ├── api/copilotkit/route.ts   CopilotKit runtime proxy
    │   │   ├── page.tsx                  Main page (CopilotKit + useAgent)
    │   │   ├── layout.tsx
    │   │   └── globals.css
    │   └── components/
    │       ├── itinerary-panel.tsx       Left panel: flights / hotels / experiences
    │       └── active-agent-badge.tsx    Agent activity indicators
    ├── package.json
    ├── tsconfig.json
    ├── next.config.ts
    └── postcss.config.mjs
```

---

## Key Technologies

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, Tailwind CSS v4 |
| AI chat UI | `@copilotkit/react-core`, `@copilotkit/react-ui` |
| Agent state hook | `useAgent` from `@copilotkit/react-core/v2` |
| Backend runtime | `@copilotkit/runtime` → `LangGraphAgent` |
| Agent framework | LangGraph (Python) with nested subgraphs |
| Backend server | FastAPI + `ag_ui_langgraph` |
| LLM | OpenAI GPT-4o-mini |

---

## How Subgraph Streaming Works

CopilotKit uses the **AG-UI protocol** (via `ag_ui_langgraph`) to stream events from LangGraph to the frontend. This includes:

- `STATE_SNAPSHOT` — full state snapshot at the start of a thread
- `STATE_DELTA` — incremental patches as state changes
- `RUN_STARTED` / `RUN_FINISHED` — lifecycle events
- `TEXT_MESSAGE_*` — streamed assistant messages

Because `ag_ui_langgraph` hooks into LangGraph's event system at the checkpoint level, state updates from **nested subgraphs** bubble up automatically — the frontend `useAgent` hook receives them the same way it receives updates from the parent graph.

Reference: [docs.copilotkit.ai/langgraph-python/subgraphs](https://docs.copilotkit.ai/langgraph-python/subgraphs)
