type AgentName = "supervisor" | "flights" | "hotels" | "experiences";

const AGENT_META: Record<
  AgentName,
  { label: string; emoji: string; color: string; dot: string }
> = {
  supervisor: {
    label: "Supervisor",
    emoji: "👨‍💼",
    color: "bg-slate-100 text-slate-700 border-slate-300",
    dot: "bg-slate-500",
  },
  flights: {
    label: "Flights",
    emoji: "✈️",
    color: "bg-indigo-50 text-indigo-700 border-indigo-200",
    dot: "bg-indigo-500",
  },
  hotels: {
    label: "Hotels",
    emoji: "🏨",
    color: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  experiences: {
    label: "Experiences",
    emoji: "🎯",
    color: "bg-violet-50 text-violet-700 border-violet-200",
    dot: "bg-violet-500",
  },
};

const ALL_AGENTS: AgentName[] = ["supervisor", "flights", "hotels", "experiences"];

interface ActiveAgentBadgeProps {
  activeAgent?: string;
  isRunning: boolean;
}

export function ActiveAgentBadge({ activeAgent, isRunning }: ActiveAgentBadgeProps) {
  const current = (activeAgent as AgentName | undefined) ?? "supervisor";

  return (
    <div className="flex flex-col items-end gap-2 shrink-0">
      {/* Running indicator */}
      {isRunning && (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-amber-200 bg-amber-50 text-amber-700 text-[10px] font-semibold uppercase tracking-wide">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
          Running
        </span>
      )}

      {/* Agent pills */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-slate-400 mr-1">Active Agent:</span>
        {ALL_AGENTS.map((name) => {
          const meta = AGENT_META[name];
          const active = isRunning && name === current;
          return (
            <span
              key={name}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-semibold uppercase tracking-wide transition-opacity ${meta.color} ${
                active ? "opacity-100 shadow-sm" : "opacity-40"
              }`}
            >
              {active && (
                <span
                  className={`w-1.5 h-1.5 rounded-full ${meta.dot} animate-pulse`}
                />
              )}
              <span aria-hidden>{meta.emoji}</span>
              <span>{meta.label}</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
