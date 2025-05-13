#!/usr/bin/env python3

import argparse
import threading
import time
import socket
import json
import os
from collections import deque, defaultdict
from typing import Dict, Deque, List, Optional
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import interp1d
import msgpack
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
import uvicorn
from datetime import datetime


# Assuming your existing modules are available
from src.models.propulsion import Propulsion
from src.simulation.simulation import Simulation
from src.models.planet import Planet
from src.models.satellite import Satellite
from src.utils.constants import Constants
from src.utils.tle_importer import TLEImporter


# Data class for satellite state
@dataclass
class SatelliteState:
    timestamp: float
    position: np.ndarray  # [x, y, z] in km
    velocity: Optional[np.ndarray] = None  # [vx, vy, vz] in km/s (optional)


# State manager for efficient storage and querying
class StateManager:
    def __init__(self, max_history: int = 3600):
        self.states: Dict[str, Deque[SatelliteState]] = {}
        self.max_history = max_history
        self.lock = threading.Lock()

    def add_state(
        self, sat_name: str, timestamp: float, position: list, velocity: list = None
    ):
        with self.lock:
            if sat_name not in self.states:
                self.states[sat_name] = deque(maxlen=self.max_history)
            state = SatelliteState(
                timestamp=timestamp,
                position=np.array(position, dtype=np.float32),
                velocity=np.array(velocity, dtype=np.float32) if velocity else None,
            )
            self.states[sat_name].append(state)

    def get_state(
        self, sat_name: str, timestamp: float = None
    ) -> Optional[SatelliteState]:
        with self.lock:
            if sat_name not in self.states:
                return None
            if timestamp is None:
                return self.states[sat_name][-1] if self.states[sat_name] else None
            return self.interpolate_state(sat_name, timestamp)

    def get_states_range(
        self, sat_name: str, start_time: float, end_time: float
    ) -> List[SatelliteState]:
        with self.lock:
            if sat_name not in self.states:
                return []
            return [
                state
                for state in self.states[sat_name]
                if start_time <= state.timestamp <= end_time
            ]

    def interpolate_state(
        self, sat_name: str, timestamp: float
    ) -> Optional[SatelliteState]:
        states = self.get_states_range(
            sat_name, timestamp - self.max_history, timestamp
        )
        if not states:
            return None
        if len(states) == 1:
            return states[0]
        times = [s.timestamp for s in states]
        positions = np.array([s.position for s in states])
        interp_func = interp1d(
            times, positions, axis=0, kind="linear", fill_value="extrapolate"
        )
        return SatelliteState(
            timestamp=timestamp,
            position=interp_func(timestamp),
            velocity=None,  # Add velocity interpolation if needed
        )

    def get_satellite_names(self) -> List[str]:
        with self.lock:
            return list(self.states.keys())

    def get_all_states(self) -> List[dict]:
        """Export all states for plotting or logging"""
        with self.lock:
            result = []
            for sat_name, states in self.states.items():
                for state in states:
                    result.append(
                        {
                            "time": state.timestamp,
                            "satellite": sat_name,
                            "position": {
                                "x": float(state.position[0]),
                                "y": float(state.position[1]),
                                "z": float(state.position[2]),
                            },
                        }
                    )
            return result


# Pydantic model for REST API responses
class SatelliteStateModel(BaseModel):
    timestamp: float
    position: List[float]
    velocity: Optional[List[float]] = None


# FastAPI state manager wrapper
class StateManagerAPI:
    def __init__(self):
        self.state_manager = StateManager()

    def update(
        self, sat_name: str, timestamp: float, position: list, velocity: list = None
    ):
        self.state_manager.add_state(sat_name, timestamp, position, velocity)


# UDP server for streaming updates
class UDPServer:
    def __init__(
        self, state_manager: StateManager, host: str = "localhost", port: int = 9999
    ):
        self.state_manager = state_manager
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.subscriptions: Dict[str, set] = {}  # sat_name -> set of client addresses
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        self.running = True
        threading.Thread(target=self.broadcast, daemon=True).start()
        threading.Thread(target=self.handle_subscriptions, daemon=True).start()

    def stop(self):
        self.running = False
        self.sock.close()

    def handle_subscriptions(self):
        self.sock.settimeout(1.0)
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                try:
                    msg = msgpack.unpackb(data)
                    sat_name = msg.get("sat_name")
                    action = msg.get("action")
                    if sat_name not in self.state_manager.get_satellite_names():
                        continue
                    with self.lock:
                        if sat_name not in self.subscriptions:
                            self.subscriptions[sat_name] = set()
                        if action == "subscribe":
                            self.subscriptions[sat_name].add(addr)
                        elif action == "unsubscribe":
                            self.subscriptions[sat_name].discard(addr)
                except Exception as e:
                    print(f"Error processing subscription: {e}")
            except socket.timeout:
                continue

    def broadcast(self):
        last_states = {}
        while self.running:
            with self.lock:
                for sat_name, addrs in self.subscriptions.items():
                    state = self.state_manager.get_state(sat_name)
                    if state:
                        # Send delta updates if position changed significantly
                        last_pos = last_states.get(sat_name, state).position
                        if not np.allclose(state.position, last_pos, atol=1e-3):
                            msg = msgpack.packb(
                                {
                                    "sat_name": sat_name,
                                    "timestamp": state.timestamp,
                                    "position": state.position.tolist(),
                                }
                            )
                            for addr in addrs:
                                try:
                                    self.sock.sendto(msg, addr)
                                except Exception as e:
                                    print(f"Error sending to {addr}: {e}")
                        last_states[sat_name] = state
            time.sleep(1.0)  # Broadcast every 1s


# Export function
def export_log(state_manager: StateManager):
    """Export the simulation log to a file"""
    print("Exporting simulation log...")
    if not os.path.exists("exports"):
        os.makedirs("exports")
    filename = f"exports/simulation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(state_manager.get_all_states(), f, indent=4)
    print(f"Log exported to {filename}")


# Simulation creation
def create_simulation(planet_name="Earth", sim_speed=1.0):
    """Create a new simulation instance"""
    planet = Planet()  # Use default Earth parameters
    dt = 1.0  # Fixed time step of 1 second
    return Simulation(planet, f"{planet_name} Simulation", sim_speed, dt)


# Add satellite from NORAD ID
def add_satellite_from_norad(
    simulation: Simulation, norad_id: str, state_manager_api: StateManagerAPI
) -> bool:
    """Add a satellite to the simulation using NORAD ID"""
    try:
        importer = TLEImporter()
        satellite = importer.fetch_satellite_by_norad_id(norad_id)
        if not satellite:
            print(f"Error: Could not find satellite with NORAD ID {norad_id}")
            return False

        orbit = importer.convert_to_simulator_orbit(satellite, simulation.m_planet)
        prop = Propulsion()
        sat = Satellite(orbit, simulation.m_planet, prop, satellite.name)

        # Handle name conflicts
        suffix = 1
        sat_name = satellite.name
        while any(
            simulation.sat(i).get_name() == sat_name for i in range(simulation.nsat())
        ):
            sat_name = f"{satellite.name}[{suffix}]"
            suffix += 1

        if sat_name != satellite.name:
            print(f"Note: Renamed satellite to {sat_name} due to name conflict")
            sat.set_name(sat_name)

        simulation.add_satellite(sat)
        print(f"Added satellite: {sat_name}")
        return True
    except Exception as e:
        print(f"Error importing satellite: {str(e)}")
        return False


# Run simulation with state updates
def run_simulation(simulation: Simulation, state_manager_api: StateManagerAPI):
    """Run the simulation in real-time until interrupted"""
    start_time = time.time()
    last_update = start_time
    dt = 1.0  # Fixed time step of 1 second

    try:
        while True:
            current_time = time.time()
            elapsed_wall_time = current_time - last_update
            if elapsed_wall_time < dt:
                time.sleep(dt - elapsed_wall_time)
                continue
            last_update = current_time

            simulation.update()

            # Update and log every second
            print(f"\nSimulation time: {simulation.t:.2f} seconds")
            for i in range(simulation.nsat()):
                sat = simulation.sat(i)
                pos = sat.get_current_position()
                sat_name = sat.get_name()
                try:
                    print(f"Satellite: {sat_name}")
                    print(
                        f"Position (km): X={pos.get_x():.2f}, Y={pos.get_y():.2f}, Z={pos.get_z():.2f}"
                    )
                    state_manager_api.update(
                        sat_name, simulation.t, [pos.get_x(), pos.get_y(), pos.get_z()]
                    )
                except Exception as e:
                    print(f"Error retrieving position: {e}")

    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
        elapsed = time.time() - start_time
        print(f"Simulation ran for {elapsed:.2f} seconds")


# FastAPI setup
app = FastAPI(title="Satellite Simulation Server")
app.add_middleware(GZipMiddleware, minimum_size=1000)
state_manager_api = StateManagerAPI()


@app.get("/satellites", response_model=List[str])
async def get_satellites():
    return state_manager_api.state_manager.get_satellite_names()


@app.get("/state/{sat_name}", response_model=SatelliteStateModel)
async def get_latest_state(sat_name: str):
    state = state_manager_api.state_manager.get_state(sat_name)
    if state is None:
        raise HTTPException(status_code=404, detail="Satellite not found")
    return SatelliteStateModel(
        timestamp=state.timestamp,
        position=state.position.tolist(),
        velocity=state.velocity.tolist() if state.velocity is not None else None,
    )


@app.get("/state/{sat_name}/history", response_model=List[SatelliteStateModel])
async def get_state_history(sat_name: str, start_time: float, end_time: float):
    states = state_manager_api.state_manager.get_states_range(
        sat_name, start_time, end_time
    )
    if not states:
        raise HTTPException(status_code=404, detail="No states found for satellite")
    return [
        SatelliteStateModel(
            timestamp=state.timestamp,
            position=state.position.tolist(),
            velocity=state.velocity.tolist() if state.velocity is not None else None,
        )
        for state in states
    ]


# Main function
def main():
    parser = argparse.ArgumentParser(
        description="Satellite Simulation Server (Real-Time)"
    )
    parser.add_argument(
        "--norad_ids",
        nargs="+",
        type=str,
        help="NORAD IDs of satellites to simulate",
        default=["25544"],  # ISS default
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Simulation speed multiplier (default: 1.0)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Enable plotting of satellite positions",
    )
    parser.add_argument(
        "--export-log",
        action="store_true",
        help="Export simulation log to a file",
    )

    args = parser.parse_args()

    if not args.norad_ids:
        print("Error: Please provide at least one NORAD ID")
        exit(1)

    # Create simulation
    sim = create_simulation(sim_speed=args.speed)

    # Add satellites
    for norad_id in args.norad_ids:
        if not add_satellite_from_norad(sim, norad_id, state_manager_api):
            exit(1)

    # Start servers
    udp_server = UDPServer(state_manager_api.state_manager)
    try:
        threading.Thread(
            target=lambda: uvicorn.run(app, host="0.0.0.0", port=8000), daemon=True
        ).start()
        udp_server.start()

        # Run simulation
        print(f"\nStarting real-time simulation with {sim.nsat()} satellites")
        print(f"Speed: {args.speed}x")
        print(f"Time step: 1.0 seconds")
        run_simulation(sim, state_manager_api)

        # Handle plotting and exporting after interruption
        if args.export_log:
            export_log(state_manager_api.state_manager)

    except KeyboardInterrupt:
        print("Shutting down servers...")
    finally:
        udp_server.stop()
        print("Server shutdown complete")


if __name__ == "__main__":
    main()
