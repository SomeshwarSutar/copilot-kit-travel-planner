import React from "react";
import type { TravelAgentState, Flight, Hotel, Experience } from "../types";
import { ActiveAgentBadge } from "./active-agent-badge";

interface ItineraryPanelProps {
  state: TravelAgentState | undefined;
  isRunning: boolean;
}

export function ItineraryPanel({ state, isRunning }: ItineraryPanelProps) {
  const { origin, destination, active_agent, flights, hotels, experiences } =
    state ?? {};

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Current Itinerary
          </h1>
          {origin && destination ? (
            <p className="mt-1 text-slate-500 text-sm">
              📍 <span className="font-medium text-slate-700">{origin}</span>
              {" → "}
              <span className="font-medium text-slate-700">{destination}</span>
            </p>
          ) : (
            <p className="mt-1 text-slate-400 text-sm italic">
              Ask the assistant to plan a trip
            </p>
          )}
        </div>

        <ActiveAgentBadge activeAgent={active_agent} isRunning={isRunning} />
      </div>

      {/* ── Flights ── */}
      <Section
        emoji="✈️"
        title="Flight Options"
        isEmpty={!flights?.length}
        emptyText="No flights found yet"
      >
        {flights?.map((f, i) => <FlightCard key={i} flight={f} />)}
      </Section>

      {/* ── Hotels ── */}
      <Section
        emoji="🏨"
        title="Hotel Options"
        isEmpty={!hotels?.length}
        emptyText="No hotels found yet"
      >
        {hotels?.map((h, i) => <HotelCard key={i} hotel={h} />)}
      </Section>

      {/* ── Experiences ── */}
      <Section
        emoji="🎯"
        title="Experiences"
        isEmpty={!experiences?.length}
        emptyText="No experiences planned yet"
      >
        {experiences?.map((e, i) => <ExperienceCard key={i} experience={e} />)}
      </Section>
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({
  emoji,
  title,
  isEmpty,
  emptyText,
  children,
}: {
  emoji: string;
  title: string;
  isEmpty: boolean;
  emptyText: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-100 bg-slate-50">
        <span className="text-lg leading-none">{emoji}</span>
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      </div>
      <div className="p-4">
        {isEmpty ? (
          <p className="text-slate-400 text-sm italic">{emptyText}</p>
        ) : (
          <div className="space-y-3">{children}</div>
        )}
      </div>
    </div>
  );
}

// ── Flight card ───────────────────────────────────────────────────────────────

function FlightCard({ flight }: { flight: Flight }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-slate-900 text-sm">
          {flight.airline}
        </span>
        <span className="text-indigo-600 font-bold text-sm">{flight.price}</span>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-600">
        <span>{flight.origin}</span>
        <span className="text-slate-400">→</span>
        <span>{flight.destination}</span>
      </div>
      <div className="flex items-center gap-3 text-xs text-slate-500">
        <span>🛫 {flight.departure}</span>
        <span className="text-slate-300">|</span>
        <span>🛬 {flight.arrival}</span>
      </div>
    </div>
  );
}

// ── Hotel card ────────────────────────────────────────────────────────────────

function HotelCard({ hotel }: { hotel: Hotel }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-slate-900 text-sm">{hotel.name}</span>
        <span className="text-emerald-600 font-bold text-sm">
          {hotel.price_per_night}/night
        </span>
      </div>
      <p className="text-xs text-slate-500">📍 {hotel.location}</p>
      <p className="text-xs text-amber-600">⭐ {hotel.rating}</p>
    </div>
  );
}

// ── Experience card ───────────────────────────────────────────────────────────

function ExperienceCard({ experience }: { experience: Experience }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-slate-900 text-sm">
          {experience.name}
        </span>
        <span className="text-violet-600 font-bold text-sm">
          {experience.price}
        </span>
      </div>
      <p className="text-xs text-slate-600">{experience.description}</p>
      <p className="text-xs text-slate-400">⏱ {experience.duration}</p>
    </div>
  );
}
