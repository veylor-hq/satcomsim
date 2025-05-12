#!/usr/bin/env python3

import json
import sys
import time
import argparse
from datetime import datetime
from src.Propulsion import Propulsion
from src.Simulation import Simulation
from src.Planet import Planet
from src.Satellite import Satellite
from src.Constants import Constants
from src.NORAD.TLE_Importer import TLEImporter
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from collections import defaultdict

step_log = []

def plot_positions():
    """Plot the positions of satellites over time"""
    print("Plotting satellite positions...")
    print(len(step_log), "steps recorded")

    from mpl_toolkits.mplot3d import Axes3D
    import matplotlib.pyplot as plt

    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")

    # Group positions by satellite
    positions_by_satellite = defaultdict(lambda: {"x": [], "y": [], "z": []})

    for entry in step_log:
        sat = entry["satellite"]
        pos = entry["position"]
        positions_by_satellite[sat]["x"].append(pos["x"])
        positions_by_satellite[sat]["y"].append(pos["y"])
        positions_by_satellite[sat]["z"].append(pos["z"])

    # Plot each satellite's points at once
    for sat, coords in positions_by_satellite.items():
        ax.scatter(coords["x"], coords["y"], coords["z"], label=sat, s=1)  # s=1 to reduce marker size

    ax.set_xlabel("X Position (km)")
    ax.set_ylabel("Y Position (km)")
    ax.set_zlabel("Z Position (km)")
    ax.legend(markerscale=5)
    plt.show()

def export_log():
    """Export the simulation log to a file"""
    print("Exporting simulation log...")
    filename = f"simulation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w") as f:
        json.dump(step_log, f, indent=4)
    print(f"Log exported to {filename}")


def create_simulation(planet_name="Earth", sim_speed=1.0, dt=1.0):
    """Create a new simulation instance"""
    planet = Planet()  # Use default Earth parameters
    return Simulation(planet, f"{planet_name} Simulation", sim_speed, dt)


def add_satellite_from_norad(simulation, norad_id):
    """Add a satellite to the simulation using NORAD ID"""
    try:
        importer = TLEImporter()
        satellite = importer.fetch_satellite_by_norad_id(norad_id)

        if not satellite:
            print(f"Error: Could not find satellite with NORAD ID {norad_id}")
            return False

        # Convert to simulator orbit parameters
        orbit = importer.convert_to_simulator_orbit(satellite, simulation.m_planet)

        # Create and configure the satellite
        prop = Propulsion()
        sat = Satellite(orbit, simulation.m_planet, prop, satellite.name)

        # Check for name conflicts and rename if necessary
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

        # Add to simulation
        simulation.add_satellite(sat)
        print(f"Added satellite: {sat_name}")
        return True

    except Exception as e:
        print(f"Error importing satellite: {str(e)}")
        return False


def run_simulation(simulation, duration, output_interval=10, realtime=False):
    """Run the simulation for a specified duration"""
    start_time = time.time()
    next_output = output_interval
    last_update = start_time

    while simulation.t < duration:
        current_time = time.time()

        if realtime:
            # In realtime mode, wait until enough wall time has passed
            elapsed_wall_time = current_time - last_update
            if elapsed_wall_time < simulation.dt:
                time.sleep(0.001)  # Small sleep to prevent CPU spinning
                continue
            last_update = current_time

        simulation.update()

        # Print status at intervals
        if simulation.t >= next_output:
            print(f"\nSimulation time: {simulation.t:.2f} seconds")
            for i in range(simulation.nsat()):
                sat = simulation.sat(i)
                pos = sat.get_current_position()
                print(f"Satellite: {sat.get_name()}")
                try:
                    print(
                        f"Position (km): X={pos.get_x():.2f}, Y={pos.get_y():.2f}, Z={pos.get_z():.2f}"
                    )
                    step_log.append(
                        {
                            "time": simulation.t,
                            "satellite": sat.get_name(),
                            "position": {
                                "x": pos.get_x(),
                                "y": pos.get_y(),
                                "z": pos.get_z(),
                            },
                        }
                    )
                except Exception as e:
                    print(f"Error retrieving position: {e}")
                    print(pos)
            next_output += output_interval

    elapsed = time.time() - start_time
    print(f"\nSimulation completed in {elapsed:.2f} seconds")


def main():
    parser = argparse.ArgumentParser(description="Satellite Simulator CLI")
    parser.add_argument(
        "--norad-ids",
        nargs="+",
        type=str,
        help="NORAD IDs of satellites to simulate",
        default=["25544"],
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=86400,
        help="Simulation duration in seconds (default: 86400)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Simulation speed multiplier (default: 1.0)",
    )
    parser.add_argument(
        "--dt", type=float, default=1.0, help="Time step in seconds (default: 1.0)"
    )
    parser.add_argument(
        "--output-interval",
        type=float,
        default=10,
        help="Status output interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Run simulation in real time, matching wall clock time",
    )

    parser.add_argument(
        "--plot",
        action="store_true",
        help="Enable plotting of satellite positions",
        default=False,   
    )

    parser.add_argument(
        "--export-log",
        action="store_true",
        help="Export simulation log to a file",
        default=False,
    )

    args = parser.parse_args()

    if not args.norad_ids:
        print("Error: Please provide at least one NORAD ID")
        sys.exit(1)

    # Create simulation
    sim = create_simulation(sim_speed=args.speed, dt=args.dt)

    # Add satellites
    for norad_id in args.norad_ids:
        if not add_satellite_from_norad(sim, norad_id):
            sys.exit(1)

    # Run simulation
    print(f"\nStarting simulation with {sim.nsat()} satellites")
    print(f"Duration: {args.duration} seconds")
    print(f"Speed: {args.speed}x")
    print(f"Time step: {args.dt} seconds")

    run_simulation(sim, args.duration, args.output_interval, args.realtime)

    if args.plot:
        plot_positions()

    if args.export_log:
        export_log()

if __name__ == "__main__":
    main()
