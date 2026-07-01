import { CopilotKit, useCoAgent } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";
import { ItineraryPanel } from "./components/itinerary-panel";
import type { TravelAgentState } from "./types";

// ── Root ──────────────────────────────────────────────────────────────────────
// runtimeUrl="/api/copilotkit" resolves to:
//   • Dev:  http://localhost:5173/api/copilotkit → proxied by Vite to FastAPI
//   • Prod: same origin, served directly by FastAPI

export default function App() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="travel_planner">
      <DemoContent />
    </CopilotKit>
  );
}

// ── Inner content (must live inside CopilotKit) ───────────────────────────────

function DemoContent() {
  // useCoAgent reads + subscribes to the LangGraph agent's state.
  // `running` is true while the Python graph is executing.
  const { state, running } = useCoAgent<TravelAgentState>({
    name: "travel_planner",
    initialState: {
      flights: [],
      hotels: [],
      experiences: [],
      active_agent: "",
    },
  });

  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50">
      {/* Left panel — live itinerary */}
      <section className="flex-1 min-w-0 overflow-y-auto p-6">
        <ItineraryPanel state={state} isRunning={running ?? false} />
      </section>

      {/* Right panel — CopilotKit chat (connects to FastAPI) */}
      <aside className="w-100 shrink-0 flex flex-col border-l border-slate-200 bg-white shadow-sm">
        <CopilotChat
          className="flex-1 min-h-0"
          labels={{
            title: "Travel Planning Assistant",
            initial:
              "Plan your perfect trip with AI specialists!\n\nTry: **Plan a trip from Amsterdam to San Francisco**",
            placeholder: "Where would you like to travel?",
          }}
          instructions={
            "You are a friendly travel planning assistant. " +
            "Help users plan trips by coordinating flights, hotels and experiences. " +
            "Keep responses concise and upbeat."
          }
        />
      </aside>
    </div>
  );
}
