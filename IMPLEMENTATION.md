# Implementation Guide — Travel Planner (CopilotKit + LangGraph + AG-UI)

This document explains how the application works end-to-end: the libraries
involved, the protocols they use, and why each piece is designed the way it is.

---

## Table of Contents

1. [Technology Overview](#1-technology-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [LangChain](#3-langchain)
4. [LangGraph](#4-langgraph)
5. [AG-UI Protocol](#5-ag-ui-protocol)
6. [CopilotKit](#6-copilotkit)
7. [Backend — FastAPI Entry-Point](#7-backend--fastapi-entry-point)
8. [Frontend — React / Vite](#8-frontend--react--vite)
9. [Request / Response Lifecycle](#9-request--response-lifecycle)
10. [Key Design Decisions & Pitfalls](#10-key-design-decisions--pitfalls)

---

## 1. Technology Overview

| Layer | Library / Tool | Role |
|-------|---------------|------|
| LLM abstraction | LangChain (`langchain-core`, `langchain-google-genai`) | Uniform interface to Google Gemini; message types; output parsers |
| Agent orchestration | LangGraph | Stateful, checkpointed graph of nodes; nested subgraphs |
| Agent ↔ UI protocol | AG-UI (`ag-ui-langgraph`, `ag_ui.core`) | SSE event stream that carries state deltas, text messages, and lifecycle events |
| Backend AI runtime | CopilotKit Python SDK (`copilotkit`) | `LangGraphAGUIAgent` — adapts a compiled LangGraph graph to the AG-UI protocol |
| Backend web server | FastAPI + Uvicorn | Serves the unified `/api/copilotkit` endpoint and the static Vite build |
| Frontend AI UI | CopilotKit React SDK (`@copilotkit/react-core`, `@copilotkit/react-ui`) | `CopilotKit` provider, `useCoAgent` hook, `CopilotChat` component |
| Frontend framework | Vite + React 19 + TypeScript | SPA build; dev-time proxy to FastAPI |

---

## 2. High-Level Architecture

```
Browser (React SPA)
  │
  │  POST /api/copilotkit          (single-endpoint transport)
  │  ← SSE event stream            (AG-UI events)
  │
FastAPI  :8123
  │
  ├─ copilotkit.LangGraphAGUIAgent
  │       │
  │       └─ ag_ui_langgraph.LangGraphAgent.run()
  │               │
  │               └─ LangGraph graph.astream_events()
  │                       │
  │                       ├─ supervisor_node   (Gemini function-calling)
  │                       ├─ flights_subgraph  (Gemini JSON generation)
  │                       ├─ hotels_subgraph   (Gemini JSON generation)
  │                       ├─ experiences_subgraph
  │                       └─ coordinator_node
  │
  └─ Static Vite build (ui/dist/) — served as SPA fallback
```

---

## 3. LangChain

LangChain (`langchain-core`) provides the foundational primitives:

### Message Types

All LangGraph state and LLM calls use LangChain's typed message classes:

| Class | Role |
|-------|------|
| `SystemMessage` | Instructions passed to the LLM (not shown in chat UI) |
| `HumanMessage` | User input or synthetic trigger messages |
| `AIMessage` | LLM response; added to `TravelState.messages` to appear in the chat UI |
| `BaseMessage` | Common base for all of the above |

### ChatGoogleGenerativeAI

```python
_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
```

This is the `langchain_google_genai` integration. It wraps the Google Generative AI API
and conforms to LangChain's `BaseChatModel` interface, so it works identically
to any other LangChain model.

### Structured Output

The supervisor node uses:

```python
structured = _model.with_structured_output(_SupervisorDecision, method="function_calling")
```

`method="function_calling"` is critical: it forces Gemini to return the structured
response via its native function-calling interface (output lands in `tool_calls`,
**not** in the text `content` field). Without this, `ag_ui_langgraph` would
intercept the raw JSON string from the `content` field and stream it to the
browser as a visible chat message.

### Output Parsers (subgraph nodes)

The flight/hotel/experience nodes use plain `.invoke()` with a `SystemMessage`
that asks for a JSON array. The response is parsed manually with `json.loads()`,
with a hardcoded fallback if parsing fails.

---

## 4. LangGraph

LangGraph orchestrates the agent as a directed graph with persistent checkpointed
state.

### State Schema — `TravelState`

```python
class TravelState(TypedDict):
    messages:         Annotated[list[BaseMessage], add_messages]
    origin:           str
    destination:      str
    flights:          list[Flight]
    hotels:           list[Hotel]
    experiences:      list[Experience]
    active_agent:     str
    needs_flights:    bool
    needs_hotels:     bool
    needs_experiences: bool
```

#### `add_messages` reducer

`messages` uses `add_messages` from `langgraph.graph.message` instead of the
plain `add` (list concatenation) reducer. This is essential:

- `add_messages` deduplicates by message `id` — when the frontend re-sends the
  full conversation history on every run, existing messages are updated in-place
  rather than appended again, preventing exponential message duplication.
- Plain `add` would append the entire history on each request, causing the same
  message to appear dozens of times in the state and the chat UI.

### Graph Structure

```
START
  └─► supervisor_node
          │
          ├─► flights_subgraph  ──► (needs_hotels?) ──► hotels_subgraph
          │                                                    │
          │                                         (needs_experiences?)
          │                                                    │
          ├─► hotels_subgraph   ──► (needs_experiences?) ──► experiences_subgraph
          │                                                    │
          ├─► experiences_subgraph ──────────────────────► coordinator_node ──► END
          │
          └─► END   (direct answer, no sub-agents)
```

#### Supervisor node

- Calls Gemini with `with_structured_output(_SupervisorDecision, method="function_calling")`
- Extracts: `origin`, `destination`, `needs_flights`, `needs_hotels`,
  `needs_experiences`, `message`
- Sets routing flags on state; conditionally appends an `AIMessage` (only when
  no sub-agents are needed — otherwise the coordinator produces the reply)

#### Subgraph nodes

Each subgraph is a separately compiled `StateGraph` that shares `TravelState`.
Nesting compiled subgraphs as nodes in the parent graph lets LangGraph
checkpoint them independently and stream their state updates as they complete.

#### Coordinator node

Runs after all needed subgraphs finish. Reads `flights`, `hotels`, `experiences`
from state and produces a summary `AIMessage`.

### Memory / Checkpointing

```python
graph = _wf.compile(checkpointer=MemorySaver())
```

`MemorySaver` keeps the full graph state in memory, keyed by `thread_id`. This
allows conversation continuity across multiple turns within the same session.

---

## 5. AG-UI Protocol

AG-UI (Agent–User Interface) is an open SSE-based protocol for streaming agent
state and events to a browser UI in real time.

### Event types used in this project

| Event | When emitted | What the frontend does |
|-------|-------------|------------------------|
| `RUN_STARTED` | Beginning of every agent run | Marks the run as active |
| `STEP_STARTED` / `STEP_FINISHED` | Each LangGraph node entry/exit | Updates the `active_agent` badge |
| `TEXT_MESSAGE_START` | LLM begins generating a visible reply | Creates a new streaming message bubble |
| `TEXT_MESSAGE_CONTENT` | Each text chunk from the LLM | Appends to the streaming bubble |
| `TEXT_MESSAGE_END` | LLM finishes the message | Closes the streaming bubble |
| `STATE_SNAPSHOT` | After each node completes | Replaces the full agent state in `useCoAgent` |
| `STATE_DELTA` | Incremental state patches | Applies a JSON-patch diff to agent state |
| `MESSAGES_SNAPSHOT` | End of run | Canonical final list of chat messages |
| `RUN_FINISHED` | End of run | Marks the run as inactive |

### SSE encoding

`ag_ui.encoder.EventEncoder` serialises each event object to an
`data: {...}\n\n` SSE frame. The `accept` header from the browser controls
whether it uses SSE format or newline-delimited JSON (NDJSON).

### `RunAgentInput`

Every agent run starts with a `RunAgentInput` (defined in `ag_ui.core`):

```python
class RunAgentInput(ConfiguredBaseModel):
    thread_id:      str           # identifies the conversation thread
    run_id:         str           # unique ID for this run
    state:          Any           # current agent state (from frontend)
    messages:       List[Message] # full conversation history
    tools:          List[Tool]    # available frontend tools
    context:        List[Context] # additional context
    forwarded_props: Any          # arbitrary props from CopilotKit provider
```

All field names are camelCase in JSON (`threadId`, `runId`, etc.) via Pydantic's
`alias_generator=to_camel`.

---

## 6. CopilotKit

CopilotKit is the glue between the React UI and the LangGraph agent. It has a
Python SDK (backend) and a React SDK (frontend).

### Python SDK — `LangGraphAGUIAgent`

```python
from copilotkit import LangGraphAGUIAgent

_agent = LangGraphAGUIAgent(
    name="travel_planner",
    description="AI travel planning assistant...",
    graph=graph,          # compiled LangGraph CompiledStateGraph
)
```

`LangGraphAGUIAgent` extends `ag_ui_langgraph.LangGraphAgent`. Its key
responsibilities:

- Wraps `graph.astream_events()` to produce AG-UI events
- Filters CopilotKit-specific custom events (`ManuallyEmitMessage`,
  `ManuallyEmitToolCall`, `ManuallyEmitState`)
- Exposes `.run(input: RunAgentInput)` as an async generator of AG-UI events
- Exposes `.clone()` to create a fresh per-request instance (avoids shared
  mutable state across concurrent requests)

### Single-Endpoint Transport Protocol

`@copilotkit/react-core` v1.61+ defaults to `useSingleEndpoint: true`, which
means **all** communication goes to a single `POST runtimeUrl` endpoint. The
body is a JSON envelope with a `method` field:

| `method` | Payload | Backend action |
|----------|---------|----------------|
| `"info"` | — | Return agent capabilities (`{ agents: { id: { description, capabilities } } }`) |
| `"agent/run"` | `{ params: { agentId }, body: RunAgentInput }` | Run the agent; return SSE stream |
| `"agent/connect"` | — | WebSocket/Phoenix handshake (acknowledged, not used here) |
| `"agent/stop"` | `{ params: { agentId, threadId } }` | Abort signal (acknowledged, not used here) |

The `"info"` response **must** use an object (map) for `agents`, keyed by agent
ID:

```json
{
  "sdkVersion": "0.0.0",
  "actions": {},
  "agents": {
    "travel_planner": {
      "description": "...",
      "capabilities": {}
    }
  }
}
```

Using an array instead causes the JS SDK to register agent ID `"0"` (the array
index) instead of `"travel_planner"`, breaking `useCoAgent`.

### React SDK

#### `CopilotKit` provider

```tsx
<CopilotKit runtimeUrl="/api/copilotkit" agent="travel_planner">
```

- `runtimeUrl` — the backend endpoint (proxied by Vite in dev)
- `agent` — the default agent ID; creates a `ProxiedCopilotRuntimeAgent`
  (extends `HttpAgent` from `@ag-ui/client`) that routes all requests

On mount, `CopilotKit` calls `fetchRuntimeInfo()` which POSTs
`{ "method": "info" }` to discover available agents, then registers them in its
internal `agents` map.

#### `useCoAgent` hook

```tsx
const { state, running } = useCoAgent<TravelAgentState>({
  name: "travel_planner",
  initialState: { flights: [], hotels: [], experiences: [], active_agent: "" },
});
```

- Subscribes to `STATE_SNAPSHOT` and `STATE_DELTA` events for the named agent
- Re-renders whenever state changes during a run
- `running` is `true` between `RUN_STARTED` and `RUN_FINISHED`
- `state` mirrors `TravelState` on the Python side (flights, hotels,
  experiences, active_agent)

#### `CopilotChat` component

Pre-built chat UI that:
- Renders conversation messages from `MESSAGES_SNAPSHOT`
- Shows streaming text from `TEXT_MESSAGE_*` events in real time
- Sends new user messages which trigger a new `agent/run` request

---

## 7. Backend — FastAPI Entry-Point

`agent/main.py` serves as both the AI runtime and the static file server.

### Unified endpoint

```python
@app.post("/api/copilotkit", response_model=None)
async def copilotkit_endpoint(request: Request):
    body = await request.json()

    if body.get("method") == "info":
        return JSONResponse({ "agents": { _agent.name: {...} } })

    if body.get("method") in ("agent/stop", "agent/connect"):
        return JSONResponse({"ok": True})

    if body.get("method") == "agent/run":
        input_data = RunAgentInput.model_validate(body["body"])
        # ... stream AG-UI events
        return StreamingResponse(event_stream(), media_type=...)

    # Fallback: raw RunAgentInput (direct AG-UI clients)
    input_data = RunAgentInput.model_validate(body)
    return StreamingResponse(event_stream(), ...)
```

`response_model=None` is required because FastAPI cannot infer a Pydantic
response model from `StreamingResponse | JSONResponse`.

### Why not `add_fastapi_endpoint` from `copilotkit.integrations.fastapi`?

The library helper registers the route as `{prefix}/{path:path}` (requires a
trailing slash or subpath). The single-endpoint transport posts to `{prefix}`
exactly (no trailing slash), which Starlette's `{path:path}` converter does
not match. The request then falls through to the SPA fallback (GET-only) and
returns **405 Method Not Allowed**.

### SPA fallback

```python
@app.get("/{full_path:path}")
async def serve_spa(full_path: str) -> FileResponse:
    target = _STATIC_DIR / full_path
    if target.is_file():
        return FileResponse(str(target))
    return FileResponse(str(_STATIC_DIR / "index.html"))
```

This only runs in production (after `npm run build`). The SPA fallback is
registered **after** the API routes, so `/api/copilotkit` is handled correctly.
The fallback is GET-only; POST requests that reach it return 405 — this is
intentional since no POST should reach the SPA.

---

## 8. Frontend — React / Vite

### Dev proxy

`ui/vite.config.ts` proxies all `/api/*` requests to `http://localhost:8123`:

```ts
proxy: {
  "/api": { target: "http://localhost:8123", changeOrigin: true }
}
```

This avoids CORS during development and mirrors the production layout where
FastAPI serves both the API and the static files from the same origin.

### State type mirroring

`ui/src/types.ts` mirrors the Python `TravelState`:

```ts
export interface TravelAgentState {
  flights:      Flight[];
  hotels:       Hotel[];
  experiences:  Experience[];
  active_agent: string;
}
```

CopilotKit's `STATE_SNAPSHOT` events carry the full Python state as JSON;
`useCoAgent<TravelAgentState>` deserialises it into this TypeScript type
automatically.

### Component layout

```
App.tsx
  ├─ CopilotKit         (provider — manages transport, agent registry, state)
  └─ DemoContent
       ├─ ItineraryPanel  (left — renders flights/hotels/experiences from state)
       └─ CopilotChat     (right — chat UI; sends messages, renders responses)
```

---

## 9. Request / Response Lifecycle

A complete turn — user types *"Plan a trip from Amsterdam to San Francisco"*:

```
1. User submits message
   CopilotChat → POST /api/copilotkit
   body: { method: "agent/run", params: { agentId: "travel_planner" },
           body: { threadId, runId, messages: [...], state: {...}, ... } }

2. FastAPI copilotkit_endpoint
   → RunAgentInput.model_validate(body["body"])
   → _agent.clone().run(input_data)      ← async generator

3. LangGraphAGUIAgent.run()
   → Calls LangGraph graph with thread_id from input
   → graph.astream_events(input, config)

4. SSE stream begins
   data: {"type":"RUN_STARTED", ...}

5. supervisor_node runs
   data: {"type":"STEP_STARTED","stepName":"supervisor"}
   Gemini (function_calling) → _SupervisorDecision
     { needs_flights: true, needs_hotels: true, needs_experiences: true,
       origin: "Amsterdam", destination: "San Francisco" }
   data: {"type":"STEP_FINISHED","stepName":"supervisor"}

6. flights_subgraph runs
   data: {"type":"STEP_STARTED","stepName":"flights"}
   Gemini → JSON array of 2 flights
   state.flights updated
   data: {"type":"STATE_DELTA", delta: [{op:"replace", path:"/flights", value:[...]}]}
   data: {"type":"STEP_FINISHED","stepName":"flights"}

7. hotels_subgraph runs  (same pattern → STATE_DELTA for hotels)

8. experiences_subgraph runs  (same pattern → STATE_DELTA for experiences)

9. coordinator_node runs
   Generates summary AIMessage
   data: {"type":"TEXT_MESSAGE_START", ...}
   data: {"type":"TEXT_MESSAGE_CONTENT", delta: "I've found ..."}
   data: {"type":"TEXT_MESSAGE_END", ...}

10. Run finishes
    data: {"type":"STATE_SNAPSHOT", snapshot: { flights:[...], hotels:[...], ... }}
    data: {"type":"MESSAGES_SNAPSHOT", messages: [...]}
    data: {"type":"RUN_FINISHED", ...}

11. Frontend
    useCoAgent re-renders with new flights/hotels/experiences
    ItineraryPanel shows all results
    CopilotChat shows the coordinator's summary message
```

---

## 10. Key Design Decisions & Pitfalls

### `add_messages` vs `add`

| Reducer | Behaviour | Problem if wrong |
|---------|-----------|-----------------|
| `add` (operator) | Concatenates lists unconditionally | Every run appends the full conversation history → exponential duplication |
| `add_messages` (langgraph) | Deduplicates by message `id`; updates existing, appends new | Correct behaviour for multi-turn conversations |

### `method="function_calling"` on supervisor

The supervisor LLM call uses `with_structured_output(_SupervisorDecision, method="function_calling")`.

Without `method="function_calling"`, Gemini uses JSON-schema/text mode: the
structured response is in the text `content` field. `ag_ui_langgraph` intercepts
every `on_chat_model_stream` event and emits `TEXT_MESSAGE_*` events for
non-empty content — so the raw JSON `{"origin": "", "needs_flights": true, ...}`
appears in the chat UI as the assistant's reply.

With function calling, the output is in `tool_calls` (content is empty), so no
`TEXT_MESSAGE_*` event is emitted for the supervisor's LLM call.

### Single-endpoint routing pitfall

`@copilotkit/react-core` v1.61+ POSTs all requests to the bare `runtimeUrl`
(`/api/copilotkit`) with a `method` field in the body. This is incompatible with
the library-provided `add_fastapi_endpoint` helper, which registers the route as
`/api/copilotkit/{path:path}` — a pattern that does not match requests to the
bare path. The custom unified handler in `main.py` was written to address this.

### Info response format

The `"info"` response `agents` field must be an **object** (keyed by agent ID),
not an array. The JS SDK calls `Object.entries(runtimeInfo.agents)` and uses the
key as the agent ID. An array causes the index `"0"` to be registered as the
agent ID instead of `"travel_planner"`.

### Gemini requires a user message

The Google Gemini API rejects requests where `contents` is empty. A
`SystemMessage` alone does not populate `contents`. All subgraph LLM calls
include an explicit `HumanMessage(content="Generate ... now.")` to satisfy this
requirement.

### `response_model=None` on FastAPI route

FastAPI infers response models from return type annotations. `StreamingResponse | JSONResponse`
is not a valid Pydantic field type. The `response_model=None` parameter disables
this inference while still allowing multiple return types.

### Message IDs and deduplication

AI messages added by `supervisor_node` and `coordinator_node` use
`AIMessage(content=...)` without an explicit `id`. LangGraph assigns `None` as
the ID. Multiple null-ID messages are not deduplicated by `add_messages` (no ID
to match on). This is acceptable for assistant messages since they represent
distinct responses, but user messages — which do have stable UUIDs from the
frontend — are correctly deduplicated.
