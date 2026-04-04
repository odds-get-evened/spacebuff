# SpaceBuff: 3D Air Traffic Control & Collision Avoidance Simulator

**SpaceBuff** is a high-performance, 3D Python simulation built on the Ursina Engine. It models the flight paths, inertia, and predictive collision avoidance (TCAS) of heavy commercial aircraft operating on a true-to-scale planetary curvature.

## 🌟 Key Features

* **Predictive Collision Avoidance (TCAS):** A 120-second lookahead engine constantly scans the fleet. If a breach of the 5-Nautical-Mile (9.26 km) horizontal or 1,000-foot vertical separation standard is predicted, the engine automatically commands divergent headings and climbs/descents.
* **Heavy Aircraft Physics:** Aircraft (A330s, MD-11s, B757s) do not turn instantly. The simulation models realistic inertia and wide turn radii (approx. 1.5 degrees per second). 
* **True-Scale Planet:** The math engine operates at a strict `1 unit = 1 kilometer` scale over a 1,000 km radius Earth sphere, allowing for massive, globe-spanning flight routes.
* **LNAV / VNAV Routing:** Planes generate multi-stop routes across randomized surface airports, climbing to cruise altitude (FL150 - FL250) and gliding down to surface waypoints automatically.
* **Automated Logbook:** Every resolution advisory issued by the TCAS engine is timestamped and recorded to a local CSV file for later analysis.

---

## 🛠️ Prerequisites & Installation

SpaceBuff requires **Python 3.8+**. The only external dependency required to run the simulation is the Ursina game engine.

1. Clone or download the repository to your local machine.
2. Open your terminal or command prompt.
3. Install Ursina via pip:
   ```bash
   pip install ursina
   ```

---

## 🚀 How to Run

Navigate to the directory containing the simulation files and execute the main Python script:

```bash
python spacebuff_ursina.py
```

*Note: Upon launch, the simulation engine runs at a `TIME_WARP` of 50x to allow heavy aircraft to complete turns and cover global distances in an observable timeframe.*

---

## 🎮 Controls & Navigation

SpaceBuff features a custom **Orbital Tracking Camera** designed for seamless air traffic monitoring.

### Camera Movements
* **Orbit (Rotate):** Hold **Left-Click** and drag the mouse to rotate the camera around your current target.
* **Pan (Drag):** Hold **Right-Click** and drag the mouse to slide the map up, down, left, or right without losing your orientation.
* **Zoom:** Use the **Mouse Wheel** to zoom in and out. The camera will smoothly glide to the new zoom level.

### Fleet Monitoring (Target Lock)
* **`TAB`:** Cycles through the active fleet. The camera will instantly lock onto the selected aircraft, tracking its exact movements and following its flight path.
* **`ESC`:** Breaks the target lock, zooming the camera back out to the global Earth view.

---

## 📊 The TCAS Logbook

Whenever the Predictive Engine intervenes to prevent a loss of separation, it writes an entry to `tcas_logbook.csv` (generated automatically in the same folder as the script). 

The logbook records:
* **Timestamp:** The exact local time of the event.
* **Aircraft 1 & Aircraft 2:** The callsigns of the conflicting traffic (e.g., `MD-11-004`).
* **A1 Action / A2 Action:** The commanded vertical resolution (e.g., `CLIMB` / `DESCEND`).
* **Distance (KM):** The predicted minimum distance that triggered the alert.

---

## 🛑 Troubleshooting

* **White Screen on Launch:** If you modify the script to include high-resolution image textures (like a NASA Earth map) and Ursina cannot locate the file or reads a corrupted color profile, the engine will default to a bright white material. Ensure any `.jpg` textures are in the exact same directory as the Python script.
* **Planes Circling Infinitely:** Heavy aircraft require immense space to turn. If you manually alter the `TIME_WARP` or the scale of the airports, planes may miss their waypoint trigger radius. Ensure the waypoint detection radius (currently `20.0` km) remains large enough for an A330 to comfortably intercept it.
