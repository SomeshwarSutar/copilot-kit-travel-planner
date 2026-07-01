// Shared type definitions — mirrored from the Python TravelState in agent/agent.py

export interface Flight {
  airline: string;
  origin: string;
  destination: string;
  departure: string;
  arrival: string;
  price: string;
}

export interface Hotel {
  name: string;
  location: string;
  rating: string;
  price_per_night: string;
}

export interface Experience {
  name: string;
  description: string;
  duration: string;
  price: string;
}

export interface TravelAgentState {
  origin?: string;
  destination?: string;
  flights?: Flight[];
  hotels?: Hotel[];
  experiences?: Experience[];
  /** Mirrors the active_agent field in Python TravelState */
  active_agent?: string;
}
