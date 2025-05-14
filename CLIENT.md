### Description
Satellite Simulator is an educational tool that allows users to create, visualize, and analyze satellite orbits around planets. The application provides a realistic 3D visualization of orbital mechanics and satellite movement, making it useful for students, educators, and space enthusiasts.


## Features
- **3D Visualization**: Real-time rendering of planets and satellites in 3D space
- **Interactive Camera**: Trackball camera controls for intuitive navigation
- **Multiple Satellites**: Create and manage multiple satellites with different orbital parameters
- **Configurable Planets**: Customize planet properties (radius, gravitational parameter, day length)
- **Orbit Customization**: Set orbital elements (semi-major axis, eccentricity, inclination, etc.)
- **Time Controls**: Adjust simulation speed and precision
- **Save/Load**: Save and load simulation configurations
- **Multiple satellite tracking**: Import satellite data from NORAD IDs using free KeepTrack.space API
- **Earth and satellite models**: Display Earth and satellite models in the simulation
- **Time control**: Play/pause simulation, adjust speed




### Basic Controls
- **Left-click and drag**: Rotate the view
- **Mouse wheel**: Zoom in/out
- **Space**: Play/pause simulation
- **F**: Increase simulation speed
- **S**: Decrease simulation speed

### Creating a New Simulation

1. Click on **File → New simulation**
2. Configure the planet parameters
3. Click "Start simulation"

### Adding a Satellite

1. Click on **Satellites → Add new satellite**
2. Configure the orbital parameters
3. Click "Add satellite"

### Configuring the Simulation

1. Click on **Simulation → Configure**
2. Adjust the time step and speed settings
3. Click "Apply and reset simulation"

### NORAD ID Tracking

The simulator can import satellite data using NORAD IDs through the free KeepTrack API:

1. Import a satellite:
   - Click "Add Satellite"
   - Enter the NORAD ID
   - The simulator will fetch the latest TLE data
   - Configure additional parameters if needed