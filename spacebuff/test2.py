from ursina import *
import random
import math


class HeavyAircraft(Entity):
    def __init__(self, position, **kwargs):
        super().__init__(
            model='cube',  # You can replace this with an actual .obj aircraft model later
            color=color.azure,
            scale=(0.5, 0.5, 1.5),  # Elongated to show heading
            position=position,
            **kwargs
        )
        self.speed = 10.0
        self.turn_speed = 30.0  # Degrees per second (slow turn rate)

        # Give it an initial random heading
        self.target_rotation_y = random.uniform(0, 360)
        self.target_rotation_x = random.uniform(-15, 15)  # Slight pitch
        self.rotation_y = self.target_rotation_y
        self.rotation_x = self.target_rotation_x

    def update(self):
        # 1. Smoothly interpolate current rotation towards target rotation (Inertia)
        # Lerp (Linear Interpolation) creates that sweeping, heavy curve.
        self.rotation_y = lerp(self.rotation_y, self.target_rotation_y, time.dt * (self.turn_speed / 100))
        self.rotation_x = lerp(self.rotation_x, self.target_rotation_x, time.dt * (self.turn_speed / 100))

        # 2. Move forward constantly in the direction it is facing
        self.position += self.forward * self.speed * time.dt

        # 3. Soft Boundary Enforcement: Instead of bouncing, gently steer back to center
        distance_from_center = distance(self.position, Vec3(0, 0, 0))
        if distance_from_center > 40:
            # Look at the center (0,0,0) to find the angle to return home
            direction_to_center = math.degrees(math.atan2(0 - self.x, 0 - self.z))
            self.target_rotation_y = direction_to_center
            self.target_rotation_x = 0


class TCASPredictiveEngine:
    """Traffic Collision Avoidance System (TCAS) style logic for heavy objects."""

    def __init__(self, threshold):
        self.threshold = threshold

    def enforce_separation(self, aircraft_list):
        num_aircraft = len(aircraft_list)
        for i in range(num_aircraft):
            for j in range(i + 1, num_aircraft):
                a1 = aircraft_list[i]
                a2 = aircraft_list[j]

                dist = distance(a1.position, a2.position)

                # If they breach the threshold, force a gradual divergence
                if dist < self.threshold:
                    # Determine vector away from the other aircraft
                    dx = a1.x - a2.x
                    dz = a1.z - a2.z

                    escape_angle_1 = math.degrees(math.atan2(dx, dz))
                    escape_angle_2 = math.degrees(math.atan2(-dx, -dz))

                    # Command a new target heading. Because of the aircraft's inertia,
                    # it will bank and turn toward this new heading slowly.
                    a1.target_rotation_y = escape_angle_1
                    a2.target_rotation_y = escape_angle_2

                    # Altitude separation (one climbs, one descends)
                    a1.target_rotation_x = -15  # Pitch up
                    a2.target_rotation_x = 15  # Pitch down


# --- Simulation Setup ---
app = Ursina()

# Create a skybox for immersion
Sky(color=color.dark_gray)

# Setup our engine and aircraft list
engine = TCASPredictiveEngine(threshold=15.0)
fleet = []

for _ in range(12):
    start_pos = Vec3(random.uniform(-20, 20), random.uniform(-20, 20), random.uniform(-20, 20))
    fleet.append(HeavyAircraft(position=start_pos))


# Ursina's global update loop
def update():
    engine.enforce_separation(fleet)


# Add an EditorCamera to let you fly around the 3D space with right-click + WASD
EditorCamera()

app.run()
