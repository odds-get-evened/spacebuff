from ursina import *
import random
import math
import csv
import time as pytime
import os
import argparse

# --- ARGUMENT PARSING FOR SPEED CONTROL ---
parser = argparse.ArgumentParser(description="SpaceBuff ATC Simulation")
parser.add_argument('-s', '--speed', type=float, default=10.0, help='Time warp speed multiplier. Lower is slower.')
args, unknown = parser.parse_known_args()

# --- SCALE & PHYSICS CONSTANTS ---
TIME_WARP = args.speed
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


class FreeFlyCamera(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        camera.parent = self
        camera.position = (0, 0, 0)
        camera.rotation = (0, 0, 0)

        self.speed = 2000
        self.mouse_sensitivity = 120
        mouse.locked = True

    def update(self):
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity
        self.rotation_x -= mouse.velocity[1] * self.mouse_sensitivity
        self.rotation_x = clamp(self.rotation_x, -90, 90)

        if held_keys['q']:
            self.rotation_y -= 100 * time.dt
        if held_keys['e']:
            self.rotation_y += 100 * time.dt

        if held_keys['w']:
            self.position += self.forward * self.speed * time.dt
        if held_keys['s']:
            self.position -= self.forward * self.speed * time.dt
        if held_keys['a']:
            self.position += self.left * self.speed * time.dt
        if held_keys['d']:
            self.position += self.right * self.speed * time.dt

    def input(self, key):
        if key == 'escape':
            mouse.locked = not mouse.locked


# --- SPHERICAL LINEAR INTERPOLATION (SLERP) ---
def generate_arc_path(p1, p2, center_y, radius, num_points=30):
    """Calculates points along the curved surface between two destinations."""
    center = Vec3(0, center_y, 0)
    v1 = p1 - center
    v2 = p2 - center

    v1_norm = v1.normalized()
    v2_norm = v2.normalized()

    # FIX: Call the .dot() method directly on the vector object
    dot_prod = v1_norm.dot(v2_norm)
    dot_prod = clamp(dot_prod, -1.0, 1.0)
    omega = math.acos(dot_prod)

    if omega == 0:
        return [p1, p2]

    arc_points = []
    for i in range(num_points + 1):
        t = i / num_points
        term1 = (math.sin((1.0 - t) * omega) / math.sin(omega)) * v1_norm
        term2 = (math.sin(t * omega) / math.sin(omega)) * v2_norm

        # Multiply by Radius + 1 so the visual line hovers slightly above the ground
        point = center + (term1 + term2) * (radius + 1)
        arc_points.append(point)

    return arc_points


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

        # Navigation altitude variables
        self.cruise_offset = random.uniform(15.0, 25.0)
        self.current_nav_offset = self.cruise_offset
        self.tcas_offset = 0.0  # Temporary altitude shift commanded by TCAS

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

        # Generate the curved plotting arcs
        route_verts = []
        for i in range(len(self.route)):
            p1 = self.route[i].position
            p2 = self.route[(i + 1) % len(self.route)].position
            # Connect the points using our new spherical math function
            arc = generate_arc_path(p1, p2, EARTH_CENTER_Y, EARTH_RADIUS, num_points=25)
            route_verts.extend(arc)

        self.route_plot = Entity(
            model=Mesh(vertices=route_verts, mode='line', thickness=2),
            color=color_theme
        )

        self.label_anchor = Entity(position=self.position, billboard=True)
        self.label_text = Text(
            parent=self.label_anchor, text="", scale=15, origin=(0, 0), color=color.white
        )

    def update(self):
        current_time = pytime.time()
        tcas_active = (current_time - self.tcas_lock_time) < (15.0 / TIME_WARP)

        if not tcas_active:
            # Bleed off the TCAS evasion altitude smoothly after the conflict resolves
            self.tcas_offset = lerp(self.tcas_offset, 0, time.dt * 0.5)

            target_port = self.route[self.current_wp_index]
            dist_to_target = math.hypot(target_port.x - self.x, target_port.z - self.z)

            if dist_to_target < 20.0:
                self.current_wp_index = (self.current_wp_index + 1) % len(self.route)
                target_port = self.route[self.current_wp_index]
                dist_to_target = math.hypot(target_port.x - self.x, target_port.z - self.z)

            dx = target_port.x - self.x
            dz = target_port.z - self.z
            self.target_heading = math.degrees(math.atan2(dx, dz))

            # Vertical Navigation Phase
            if dist_to_target > 80:
                self.current_nav_offset = self.cruise_offset
            else:
                self.current_nav_offset = (dist_to_target / 80) * self.cruise_offset

        # --- TRUE CURVATURE MATH ---
        # Calculate exactly how high the crust of the Earth is directly beneath the plane
        dist_xz = math.hypot(self.x, self.z)
        if dist_xz < EARTH_RADIUS:
            local_surface_y = EARTH_CENTER_Y + math.sqrt(EARTH_RADIUS ** 2 - dist_xz ** 2)
        else:
            local_surface_y = EARTH_CENTER_Y

        # Target altitude actively follows the curve of the Earth + cruise level + TCAS overrides
        self.target_altitude = local_surface_y + self.current_nav_offset + self.tcas_offset

        turn_step = time.dt * self.turn_speed * TIME_WARP
        self.rotation_y = lerp(self.rotation_y, self.target_heading, turn_step / 10)

        if abs(self.y - self.target_altitude) > 0.05:
            direction = 1 if self.target_altitude > self.y else -1
            self.y += direction * self.climb_rate * time.dt * TIME_WARP
            self.rotation_x = lerp(self.rotation_x, -5 * direction, time.dt)
        else:
            self.rotation_x = lerp(self.rotation_x, 0, time.dt)

        self.position += self.forward * self.speed * time.dt * TIME_WARP

        self.label_anchor.position = self.position + Vec3(0, 3, 0)
        alt_km = self.y - local_surface_y
        flight_level = int((alt_km * 3280.84) / 100)

        status_string = f"{self.ac_id}\nPos: X:{int(self.x)} Z:{int(self.z)}\nAlt: FL{flight_level}"

        if tcas_active:
            self.label_text.color = color.red
            self.label_text.text = f"{status_string}\n[ TCAS WARNING ]"
        else:
            self.label_text.color = color.rgba(255, 255, 255, 200)
            self.label_text.text = status_string

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

                        # Modify the planes' temporary TCAS offset rather than absolute Y
                        if a1.y >= a2.y:
                            a1.tcas_offset += 0.5
                            a2.tcas_offset -= 0.5
                            a1_act, a2_act = "CLIMB", "DESCEND"
                        else:
                            a1.tcas_offset -= 0.5
                            a2.tcas_offset += 0.5
                            a1_act, a2_act = "DESCEND", "CLIMB"

                        a1.tcas_lock_time = current_time
                        a2.tcas_lock_time = current_time

                        self.logbook.log_event(a1.ac_id, a2.ac_id, a1_act, a2_act, future_dist)
                        self.cooldowns[conflict_pair] = current_time


def generate_surface_coordinate(radius, center_y):
    theta = random.uniform(0, 2 * math.pi)
    phi = random.uniform(math.radians(10), math.radians(75))
    x = radius * math.sin(phi) * math.cos(theta)
    z = radius * math.sin(phi) * math.sin(theta)
    y = center_y + (radius * math.cos(phi))
    return Vec3(x, y, z)


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print(f"Initializing SpaceBuff Radar. Time Warp Factor: {TIME_WARP}x")
    app = Ursina()

    Sky(color=color.black)
    camera.clip_plane_far = 20000

    earth_surface = Entity(
        model='sphere', scale=EARTH_RADIUS * 2, color=color.dark_gray, position=(0, EARTH_CENTER_Y, 0)
    )

    logbook = CSVLogbook()
    engine = TCASPredictiveEngine(SEPARATION_MIN_KM, VERTICAL_SEP_KM, LOOKAHEAD_SECONDS, logbook)

    airports = []
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
        route_length = random.randint(3, 6)
        route = random.sample(airports, route_length)

        fleet.append(HeavyAircraft(
            ac_id=str(i + 1).zfill(3),
            route=route,
            model_type=profile["type"],
            cruise_speed_kmh=profile["speed"],
            color_theme=profile["color"]
        ))

    free_cam = FreeFlyCamera(position=(0, 1000, -2500))
    free_cam.look_at(earth_surface)


    def update():
        engine.enforce_separation(fleet)


    app.run()