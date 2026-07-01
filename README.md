# CopilotKit + LangGraph Subgraphs — Travel Planner

> **Stack**: Vite + React 19 + TypeScript frontend · FastAPI Python backend · Google Gemini LLM  
> No Node.js server in production — one `python main.py` runs everything.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       FastAPI  (port 8123)                        │
│                                                                  │
│  POST /api/copilotkit  ← unified single-endpoint handler         │
│    • {"method":"info"}        → capabilities discovery           │
│    • {"method":"agent/run"}   → LangGraph AG-UI SSE stream       │
│    • {"method":"agent/stop"}  → abort (no-op)                    │
│  /assets/*             ← Vite build output (JS/CSS)              │
│  /*                    ← SPA fallback (index.html)               │
└──────────────────────────────────────────────────────────────────┘
        ▲
        │  dev:  Vite proxy  /api → http://localhost:8123
        │  prod: same origin (no proxy needed)
┌──────────────────────────────────────────────────────────────────┐
│              Vite dev server (port 5173) — dev only               │
└──────────────────────────────────────────────────────────────────┘
```

### LangGraph subgraphs

```
Supervisor node
  ├── flights_subgraph      — generates flight options → state.flights
  ├── hotels_subgraph       — generates hotel options  → state.hotels
  └── experiences_subgraph  — plans activities         → state.experiences
        └── coordinator_node — final summary message
```

State from every subgraph streams to the React frontend in real-time via the
**AG-UI protocol** — no extra wiring needed.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| Google AI API key | — |

---

## Quick Start

### 1 — Backend

```bash
cd agent

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt

# Add your Google AI key
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
# Edit .env → GOOGLE_API_KEY=<your-key>

python main.py                  # http://localhost:8123
```

Health check: `curl http://localhost:8123/health`

### 2 — Frontend (development)

Open a **new terminal**:

```bash
cd ui
npm install
npm run dev                     # http://localhost:5173
```

Vite proxies `/api/*` to FastAPI automatically — no extra config needed.

### 3 — Production (static files served by FastAPI)

```bash
cd ui
npm run build                   # outputs ui/dist/

cd ../agent
python main.py                  # serves everything on http://localhost:8123
```

---

## Usage

Type in the chat panel (right side):

| Prompt | What happens |
|--------|-------------|
| `Plan a trip from Amsterdam to San Francisco` | All three subgraphs run — flights + hotels + experiences appear in the itinerary |
| `Find me flights from New York to Tokyo` | Only the flights subgraph runs |
| `What hotels are available in Paris?` | Only the hotels subgraph runs |
| `What can I do in Barcelona?` | Only the experiences subgraph runs |

Watch the **Active Agent** badge update in real time as each subgraph executes.

---

## Project Structure

```
copilotkit_demo/
├── .gitignore
├── README.md
│
├── agent/                        Python FastAPI backend
│   ├── agent.py                  Supervisor + subgraphs (LangGraph)
│   ├── main.py                   FastAPI entry-point + unified /api/copilotkit handler
│   ├── requirements.txt
│   └── .env.example
│
└── ui/                           Vite + React frontend
    ├── index.html
    ├── vite.config.ts            Dev proxy: /api → http://localhost:8123
    ├── package.json
    ├── tsconfig.json
    └── src/
        ├── App.tsx               CopilotKit provider + useCoAgent hook
        ├── types.ts              TravelAgentState type
        └── components/
            ├── itinerary-panel.tsx      Flights / hotels / experiences panels
            └── active-agent-badge.tsx   Real-time subgraph activity indicator
```

---

## Key Technologies

| Layer | Technology |
|-------|-----------|
| Frontend | Vite, React 19, TypeScript, Tailwind CSS v4 |
| AI chat UI | `@copilotkit/react-core`, `@copilotkit/react-ui` |
| Agent state | `useCoAgent` from `@copilotkit/react-core` |
| Backend protocol | Custom single-endpoint handler (`{"method": ...}` envelope) |
| Agent class | `LangGraphAGUIAgent` from `copilotkit` |
| AG-UI runtime | `ag_ui_langgraph`, `ag_ui.core.RunAgentInput` |
| Agent framework | LangGraph (Python) — nested subgraphs |
| Backend server | FastAPI + Uvicorn |
| LLM | Google Gemini 2.5 Flash via `langchain-google-genai` |

---

## How the Single-Endpoint Protocol Works

`@copilotkit/react-core` v1.61+ uses a **single-endpoint transport** by default:
all requests go to `runtimeUrl` (`POST /api/copilotkit`) with a `method` field in the
body that determines what the server should do:

| `method` field | Purpose |
|----------------|---------|
| `"info"` | Returns available agents as a keyed object `{ agentId: { description, capabilities } }` |
| `"agent/run"` | Runs the agent; `RunAgentInput` is nested under the `body` key of the envelope |
| `"agent/connect"` | Phoenix/WebSocket connect handshake (acknowledged, not used) |
| `"agent/stop"` | Abort signal (acknowledged, not used) |

The `RunAgentInput` is forwarded to `LangGraphAGUIAgent.run()` which streams
AG-UI SSE events (`RUN_STARTED`, `STATE_SNAPSHOT`, `STATE_DELTA`,
`TEXT_MESSAGE_*`, `RUN_FINISHED`) back to the browser.
