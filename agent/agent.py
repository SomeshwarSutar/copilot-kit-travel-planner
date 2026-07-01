"""
Travel Planning Agent — LangGraph subgraphs demo.

Architecture
------------
Parent graph (supervisor):
  START → supervisor_node
         ↓ (conditional: needs_flights?)
      flights_subgraph  → (conditional: needs_hotels?)
         ↓                    hotels_subgraph  → (conditional: needs_experiences?)
         └──────────────────────────────────────  experiences_subgraph
                                                         ↓
                                               coordinator_node → END

Each subgraph is a fully compiled StateGraph that shares the same TravelState.
CopilotKit / ag-ui-langgraph streams every state update to the frontend
automatically — no extra wiring required.
"""

from __future__ import annotations

import json
from operator import add
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from typing_extensions import TypedDict

load_dotenv()

# ── Model ─────────────────────────────────────────────────────────────────────

_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)


# ── Shared state ──────────────────────────────────────────────────────────────


class Flight(TypedDict):
    airline: str
    origin: str
    destination: str
    departure: str
    arrival: str
    price: str


class Hotel(TypedDict):
    name: str
    location: str
    rating: str
    price_per_night: str


class Experience(TypedDict):
    name: str
    description: str
    duration: str
    price: str


class TravelState(TypedDict):
    # Shared across parent + all subgraphs
    messages: Annotated[list[BaseMessage], add]
    origin: str
    destination: str
    flights: list[Flight]
    hotels: list[Hotel]
    experiences: list[Experience]
    active_agent: str  # "supervisor" | "flights" | "hotels" | "experiences"
    # Routing flags — supervisor sets them; each subgraph clears its own
    needs_flights: bool
    needs_hotels: bool
    needs_experiences: bool


# ── Flights subgraph ──────────────────────────────────────────────────────────


def _search_flights_node(state: TravelState) -> dict:
    origin = state.get("origin") or "Unknown"
    destination = state.get("destination") or "Unknown"

    resp = _model.invoke(
        [
            SystemMessage(
                content=(
                    f"Generate exactly 2 realistic flight options from {origin} to {destination}.\n"
                    "Return ONLY a valid JSON array — no prose, no markdown. Example:\n"
                    f'[{{"airline":"Delta","origin":"{origin}","destination":"{destination}",'
                    '"departure":"09:00 AM","arrival":"05:00 PM","price":"$459"}}]'
                )
            ),
            HumanMessage(content="Generate the flight options now."),
        ]
    )

    try:
        flights: list[Flight] = json.loads(resp.content)
        if not isinstance(flights, list):
            raise ValueError("not a list")
    except Exception:
        flights = [
            {
                "airline": "Delta Airlines",
                "origin": origin,
                "destination": destination,
                "departure": "09:00 AM",
                "arrival": "05:00 PM",
                "price": "$459",
            },
            {
                "airline": "United Airlines",
                "origin": origin,
                "destination": destination,
                "departure": "02:00 PM",
                "arrival": "10:00 PM",
                "price": "$389",
            },
        ]

    return {"flights": flights, "active_agent": "flights", "needs_flights": False}


_flights_wf = StateGraph(TravelState)
_flights_wf.add_node("search_flights", _search_flights_node)
_flights_wf.add_edge(START, "search_flights")
_flights_wf.add_edge("search_flights", END)
flights_subgraph = _flights_wf.compile()


# ── Hotels subgraph ───────────────────────────────────────────────────────────


def _search_hotels_node(state: TravelState) -> dict:
    destination = state.get("destination") or "Unknown"

    resp = _model.invoke(
        [
            SystemMessage(
                content=(
                    f"Generate exactly 2 realistic hotel options in {destination}.\n"
                    "Return ONLY a valid JSON array — no prose, no markdown. Example:\n"
                    f'[{{"name":"Grand Hyatt","location":"{destination}",'
                    '"rating":"4.5/5","price_per_night":"$180"}}]'
                )
            ),
            HumanMessage(content="Generate the hotel options now."),
        ]
    )

    try:
        hotels: list[Hotel] = json.loads(resp.content)
        if not isinstance(hotels, list):
            raise ValueError("not a list")
    except Exception:
        hotels = [
            {
                "name": f"{destination} Grand Hotel",
                "location": destination,
                "rating": "4.5/5",
                "price_per_night": "$180",
            },
            {
                "name": f"{destination} City Inn",
                "location": destination,
                "rating": "4.0/5",
                "price_per_night": "$99",
            },
        ]

    return {"hotels": hotels, "active_agent": "hotels", "needs_hotels": False}


_hotels_wf = StateGraph(TravelState)
_hotels_wf.add_node("search_hotels", _search_hotels_node)
_hotels_wf.add_edge(START, "search_hotels")
_hotels_wf.add_edge("search_hotels", END)
hotels_subgraph = _hotels_wf.compile()


# ── Experiences subgraph ──────────────────────────────────────────────────────


def _plan_experiences_node(state: TravelState) -> dict:
    destination = state.get("destination") or "Unknown"

    resp = _model.invoke(
        [
            SystemMessage(
                content=(
                    f"Generate exactly 3 interesting experiences/activities in {destination}.\n"
                    "Return ONLY a valid JSON array — no prose, no markdown. Example:\n"
                    '[{"name":"Golden Gate Walk","description":"Walk the iconic bridge",'
                    '"duration":"2 hours","price":"Free"}]'
                )
            ),
            HumanMessage(content="Generate the experiences now."),
        ]
    )

    try:
        experiences: list[Experience] = json.loads(resp.content)
        if not isinstance(experiences, list):
            raise ValueError("not a list")
    except Exception:
        experiences = [
            {
                "name": f"City Tour of {destination}",
                "description": "Explore the city highlights",
                "duration": "3 hours",
                "price": "$45",
            },
            {
                "name": "Local Food Tour",
                "description": f"Taste the best cuisine in {destination}",
                "duration": "4 hours",
                "price": "$75",
            },
            {
                "name": "Museum Visit",
                "description": "Explore local history and culture",
                "duration": "2 hours",
                "price": "$20",
            },
        ]

    return {
        "experiences": experiences,
        "active_agent": "experiences",
        "needs_experiences": False,
    }


_experiences_wf = StateGraph(TravelState)
_experiences_wf.add_node("plan_experiences", _plan_experiences_node)
_experiences_wf.add_edge(START, "plan_experiences")
_experiences_wf.add_edge("plan_experiences", END)
experiences_subgraph = _experiences_wf.compile()


# ── Supervisor + coordinator (parent graph) ───────────────────────────────────


class _SupervisorDecision(BaseModel):
    origin: str = ""
    destination: str = ""
    needs_flights: bool = False
    needs_hotels: bool = False
    needs_experiences: bool = False
    message: str = ""


def supervisor_node(state: TravelState) -> dict:
    """
    Reads the user's latest message and decides:
    - Which cities are involved
    - Which sub-agents to activate
    - A conversational reply (used only when no sub-agents are needed)
    """
    structured = _model.with_structured_output(_SupervisorDecision)
    decision: _SupervisorDecision = structured.invoke(
        [
            SystemMessage(
                content=(
                    "You are a travel planning coordinator.\n\n"
                    "Given the user's message, extract:\n"
                    "- origin: departure city (if mentioned)\n"
                    "- destination: arrival/destination city (if mentioned)\n"
                    "- needs_flights: true when the user wants flight options\n"
                    "- needs_hotels: true when the user wants hotel options\n"
                    "- needs_experiences: true when the user wants activities/experiences\n"
                    "- message: a warm, short conversational reply\n\n"
                    'Examples:\n'
                    '"Plan a trip from Amsterdam to San Francisco" → all needs=true, '
                    'origin="Amsterdam", destination="San Francisco"\n'
                    '"Find me flights to Paris from New York" → needs_flights=true only\n'
                    '"What can I do in Tokyo?" → needs_experiences=true only\n'
                    '"Hello" → all needs=false, message="Hi! Where would you like to travel?"'
                )
            ),
            *state["messages"],
        ]
    )

    update: dict = {
        "active_agent": "supervisor",
        "needs_flights": decision.needs_flights,
        "needs_hotels": decision.needs_hotels,
        "needs_experiences": decision.needs_experiences,
    }
    if decision.origin:
        update["origin"] = decision.origin
    if decision.destination:
        update["destination"] = decision.destination

    # Only emit a direct message if no sub-agents are being called
    if not (decision.needs_flights or decision.needs_hotels or decision.needs_experiences):
        update["messages"] = [AIMessage(content=decision.message or "How can I help you plan your trip?")]

    return update


def coordinator_node(state: TravelState) -> dict:
    """Generates a summary response after all sub-agents have finished."""
    flights = state.get("flights") or []
    hotels = state.get("hotels") or []
    experiences = state.get("experiences") or []
    destination = state.get("destination") or ""

    parts: list[str] = []
    if flights:
        parts.append(f"{len(flights)} flight option(s)")
    if hotels:
        parts.append(f"{len(hotels)} hotel option(s)")
    if experiences:
        parts.append(f"{len(experiences)} experience(s)")

    if parts:
        summary = f"I've found {', '.join(parts)}"
        if destination:
            summary += f" for your trip to **{destination}**"
        summary += ". Check the itinerary panel for details!"
    else:
        summary = "I wasn't able to find any results. Please try again with more details."

    return {
        "messages": [AIMessage(content=summary)],
        "active_agent": "supervisor",
    }


# ── Routing functions ─────────────────────────────────────────────────────────


def _route_from_supervisor(state: TravelState) -> str:
    if state.get("needs_flights"):
        return "flights"
    if state.get("needs_hotels"):
        return "hotels"
    if state.get("needs_experiences"):
        return "experiences"
    return END  # direct answer — no sub-agents needed


def _route_after_flights(state: TravelState) -> str:
    if state.get("needs_hotels"):
        return "hotels"
    if state.get("needs_experiences"):
        return "experiences"
    return "coordinator"


def _route_after_hotels(state: TravelState) -> str:
    if state.get("needs_experiences"):
        return "experiences"
    return "coordinator"


# ── Assemble parent graph ─────────────────────────────────────────────────────

_wf = StateGraph(TravelState)
_wf.add_node("supervisor", supervisor_node)
_wf.add_node("flights", flights_subgraph)
_wf.add_node("hotels", hotels_subgraph)
_wf.add_node("experiences", experiences_subgraph)
_wf.add_node("coordinator", coordinator_node)

_wf.add_edge(START, "supervisor")

_wf.add_conditional_edges(
    "supervisor",
    _route_from_supervisor,
    {"flights": "flights", "hotels": "hotels", "experiences": "experiences", END: END},
)
_wf.add_conditional_edges(
    "flights",
    _route_after_flights,
    {"hotels": "hotels", "experiences": "experiences", "coordinator": "coordinator"},
)
_wf.add_conditional_edges(
    "hotels",
    _route_after_hotels,
    {"experiences": "experiences", "coordinator": "coordinator"},
)
_wf.add_edge("experiences", "coordinator")
_wf.add_edge("coordinator", END)

graph = _wf.compile(checkpointer=MemorySaver())
