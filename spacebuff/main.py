from ursina import *
import random
import math
import csv
import time as pytime
import os

# --- SCALE & PHYSICS CONSTANTS ---
TIME_WARP = 50.0
SEPARATION_MIN_KM = 9.26
VERTICAL_SEP_KM = 0.3
LOOKAHEAD_SECONDS = 120.0
EARTH_RADIUS = 1000
EARTH_CENTER_Y = -500


class CSVLogbook:
    def __init__(self, filename="tcas_logbook.csv"):
        self.filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        with open(self.filepath, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Aircraft_1", "Aircraft_2", "A1_Action", "A2_Action", "Distance_KM"])

    def log_event(self, a1_id, a2_id, a1_action, a2_action, distance):
        with open(self.filepath, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(
                [pytime.strftime("%Y-%m-%d %H:%M:%S"), a1_id, a2_id, a1_action, a2_action, round(distance, 2)])


class FlightPathTrail(Entity):
    def __init__(self, position, trail_color, **kwargs):
        super().__init__(
            model='sphere', scale=1.5, color=trail_color, position=position, **kwargs
        )
        self.animate_color(color.clear, duration=45 / TIME_WARP)
        destroy(self, delay=45 / TIME_WARP)


class Airport(Entity):
    def __init__(self, name, position, **kwargs):
        super().__init__(
            model='sphere', color=color.red, scale=4, position=position, **kwargs
        )
        self.port_name = name


# --- UPGRADED CAMERA SYSTEM ---
class OrbitalTrackingCamera(Entity):
    def __init__(self, default_target, default_distance, **kwargs):
        super().__init__(**kwargs)
        self.default_target = default_target
        self.current_target = default_target

        self.distance = default_distance
        self.target_distance = default_distance

        # New: Allows dragging the camera off-center
        self.pan_offset = Vec3(0, 0, 0)

        camera.parent = self
        camera.position = (0, 0, -self.distance)
        camera.look_at(self.current_target)

    def focus_on(self, entity, zoom_level):
        """Locks the camera to a new entity, sets the zoom, and resets panning."""
        self.current_target = entity
        self.target_distance = zoom_level
        self.pan_offset = Vec3(0, 0, 0)  # Snap back to center when switching targets

    def input(self, key):
        if key == 'scroll up':
            self.target_distance = max(10, self.target_distance - 150)
        if key == 'scroll down':
            self.target_distance = min(5000, self.target_distance + 150)

    def update(self):
        # 1. Right-Click Drag to PAN (Slide the map around)
        if mouse.right:
            self.pan_offset += camera.right * -mouse.velocity[0] * (self.distance * 0.5)
            self.pan_offset += camera.up * -mouse.velocity[1] * (self.distance * 0.5)

        # 2. Smoothly track the target + our pan offset
        target_pos = self.current_target.position + self.pan_offset
        self.position = lerp(self.position, target_pos, time.dt * 10)

        # 3. Smoothly glide to the target zoom distance
        self.distance = lerp(self.distance, self.target_distance, time.dt * 5)
        camera.position = (0, 0, -self.distance)

        # 4. Left-Click Drag to ORBIT (Rotate around the target)
        if mouse.left:
            self.rotation_y += mouse.velocity[0] * 150
            self.rotation_x -= mouse.velocity[1] * 150
            self.rotation_x = clamp(self.rotation_x, -85, 85)


class HeavyAircraft(Entity):
    def __init__(self, ac_id, route, model_type, cruise_speed_kmh, color_theme, **kwargs):
        super().__init__(
            model='cube', color=color_theme, scale=(1.5, 1.5, 4.5), position=route[0].position, **kwargs
        )
        self.ac_id = f"{model_type}-{ac_id}"
        self.speed = (cruise_speed_kmh / 3600.0)
        self.turn_speed = 1.5
        self.climb_rate = 0.015

        self.route = route
        self.current_wp_index = 1
        self.cruise_altitude = (EARTH_CENTER_Y + EARTH_RADIUS) + random.uniform(15.0, 25.0)

        self.target_heading = self.rotation_y
        self.target_altitude = self.y
        self.tcas_lock_time = 0
        self.last_trail_drop = pytime.time()

        predictive_length = (self.speed * LOOKAHEAD_SECONDS) * 0.10
        self.predictive_line = Entity(
            parent=self, model='cube', color=color.rgba(255, 255, 255, 150),
            scale=(0.4, 0.4, predictive_length / self.scale_z),
            position=(0, 0, (predictive_length / self.scale_z) / 2 + 0.5)
        )

    def update(self):
        current_time = pytime.time()
        tcas_active = (current_time - self.tcas_lock_time) < (15.0 / TIME_WARP)

        if not tcas_active:
            target_port = self.route[self.current_wp_index]
            dist_to_target = math.hypot(target_port.x - self.x, target_port.z - self.z)

            if dist_to_target < 20.0:
                self.current_wp_index = (self.current_wp_index + 1) % len(self.route)
                target_port = self.route[self.current_wp_index]
                dist_to_target = math.hypot(target_port.x - self.x, target_port.z - self.z)

            dx = target_port.x - self.x
            dz = target_port.z - self.z
            self.target_heading = math.degrees(math.atan2(dx, dz))

            if dist_to_target > 80:
                self.target_altitude = self.cruise_altitude
            else:
                surface_y = target_port.y
                self.target_altitude = surface_y + (dist_to_target / 80) * (self.cruise_altitude - surface_y)

        turn_step = time.dt * self.turn_speed * TIME_WARP
        self.rotation_y = lerp(self.rotation_y, self.target_heading, turn_step / 10)

        if abs(self.y - self.target_altitude) > 0.05:
            direction = 1 if self.target_altitude > self.y else -1
            self.y += direction * self.climb_rate * time.dt * TIME_WARP
            self.rotation_x = lerp(self.rotation_x, -5 * direction, time.dt)
        else:
            self.rotation_x = lerp(self.rotation_x, 0, time.dt)

        self.position += self.forward * self.speed * time.dt * TIME_WARP

        if current_time - self.last_trail_drop > (1.0 / TIME_WARP):
            FlightPathTrail(position=self.position, trail_color=self.color)
            self.last_trail_drop = current_time


class TCASPredictiveEngine:
    def __init__(self, threshold_km, alt_threshold_km, lookahead_seconds, logbook):
        self.threshold_km = threshold_km
        self.alt_threshold_km = alt_threshold_km
        self.lookahead = lookahead_seconds
        self.logbook = logbook
        self.cooldowns = {}

    def enforce_separation(self, aircraft_list):
        num_aircraft = len(aircraft_list)
        current_time = pytime.time()

        for i in range(num_aircraft):
            for j in range(i + 1, num_aircraft):
                a1, a2 = aircraft_list[i], aircraft_list[j]

                if a1.y < (EARTH_CENTER_Y + EARTH_RADIUS + 3.0) and a2.y < (EARTH_CENTER_Y + EARTH_RADIUS + 3.0):
                    continue

                alt_diff = abs(a1.y - a2.y)
                if alt_diff > self.alt_threshold_km:
                    continue

                future_pos1 = a1.position + (a1.forward * a1.speed * self.lookahead)
                future_pos2 = a2.position + (a2.forward * a2.speed * self.lookahead)

                future_pos1.y, future_pos2.y = 0, 0
                future_dist = distance(future_pos1, future_pos2)

                if future_dist < self.threshold_km:
                    conflict_pair = f"{a1.ac_id}_{a2.ac_id}"

                    if current_time - self.cooldowns.get(conflict_pair, 0) > (15 / TIME_WARP):
                        dx, dz = a1.x - a2.x, a1.z - a2.z
                        a1.target_heading = math.degrees(math.atan2(dx, dz))
                        a2.target_heading = math.degrees(math.atan2(-dx, -dz))

                        if a1.y >= a2.y:
                            a1.target_altitude += 0.5
                            a2.target_altitude -= 0.5
                            a1_act, a2_act = "CLIMB", "DESCEND"
                        else:
                            a1.target_altitude -= 0.5
                            a2.target_altitude += 0.5
                            a1_act, a2_act = "DESCEND", "CLIMB"

                        a1.tcas_lock_time = current_time
                        a2.tcas_lock_time = current_time

                        self.logbook.log_event(a1.ac_id, a2.ac_id, a1_act, a2_act, future_dist)
                        self.cooldowns[conflict_pair] = current_time


def generate_surface_coordinate(radius, center_y):
    theta = random.uniform(0, 2 * math.pi)
    # FIX: Expanded the generation area from 15 degrees to 75 degrees.
    # This creates massive, globe-spanning distances between airports.
    phi = random.uniform(math.radians(10), math.radians(75))

    x = radius * math.sin(phi) * math.cos(theta)
    z = radius * math.sin(phi) * math.sin(theta)
    y = center_y + (radius * math.cos(phi))
    return Vec3(x, y, z)


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    app = Ursina()

    Sky(color=color.black)
    camera.clip_plane_far = 20000

    earth_surface = Entity(
        model='sphere', scale=EARTH_RADIUS * 2, color=color.dark_gray, position=(0, EARTH_CENTER_Y, 0)
    )

    logbook = CSVLogbook()
    engine = TCASPredictiveEngine(SEPARATION_MIN_KM, VERTICAL_SEP_KM, LOOKAHEAD_SECONDS, logbook)

    airports = []
    # Increased the number of airports to allow for more route variation
    for i in range(15):
        pos = generate_surface_coordinate(EARTH_RADIUS, EARTH_CENTER_Y)
        airports.append(Airport(name=f"Port_{i}", position=pos))

    fleet = []
    fleet_profiles = [
        {"type": "A330", "speed": 870, "color": color.azure},
        {"type": "MD-11", "speed": 940, "color": color.orange},
        {"type": "B757", "speed": 850, "color": color.green}
    ]

    for i in range(20):
        profile = random.choice(fleet_profiles)
        # FIX: Each aircraft now gets a randomized route of 3 to 6 different stops
        route_length = random.randint(3, 6)
        route = random.sample(airports, route_length)

        fleet.append(HeavyAircraft(
            ac_id=str(i + 1).zfill(3),
            route=route,
            model_type=profile["type"],
            cruise_speed_kmh=profile["speed"],
            color_theme=profile["color"]
        ))

    # --- HOTKEY LOGIC ---
    focused_index = -1


    def input(key):
        global focused_index
        if key == 'tab':
            focused_index = (focused_index + 1) % len(fleet)
            cam_pivot.focus_on(fleet[focused_index], zoom_level=30)
        elif key == 'escape':
            focused_index = -1
            cam_pivot.focus_on(earth_surface, zoom_level=2500)


    def update():
        engine.enforce_separation(fleet)


    cam_pivot = OrbitalTrackingCamera(default_target=earth_surface, default_distance=2500)
    cam_pivot.position = earth_surface.position

    app.run()
    