# Satellite Communication Simulator
## Overview
## Requirements
- Python 3.10+
- NumPy (optional for additional calculations)
- matplotlib (for satellite model visualization)
- skyfield (for satellite position calculations)
- requests (for API communication)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/veylor-hq/satcomsim.git
cd satcomsim
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Run the simulator:
```bash
python3 main.py
```

## Usage

### CLI Usage  
#### Help  
To view the command line interface (CLI) help, run:  
```bash
python3 cli.py --help
```

#### Example
To run a simulation with a specific planet and satellite, use the following command:
```bash
python3 cli.py --norad-ids 25544 --duration 86400 --speed 1.0 --dt 1.0 --output-interval 10
```
This command will simulate the International Space Station (ISS) orbiting Earth.
Add `--plot` to visualize the simulation results.   
Add `--export` to save position logs to the file.  
These commands and the rest are included in the help message.  

Some client help can temporarily be found in the [CLIENT.md](CLIENT.md) file.

## Acknowledgements

Part of this simulator(specifically general space-movement) was ported from a C++/Qt implementation to Python/PyQt5 by [Logangutknecht](https://github.com/logangutknecht/SatelliteSimulator).
The original repository can be found here by [FlorentF9](https://github.com/FlorentF9/SatelliteSimulator/).  
Most of the code are highly modified or will be rewritten completly in the future, but the original code might still be present across the repository.

## License  
This project is licensed under the Apache License Version 2.0. See the [LICENSE](LICENSE) file for details.