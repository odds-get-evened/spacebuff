import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from typing import List


class Point3D:
    """Represents a moving point in 3D space."""

    def __init__(self, id: int, position: np.ndarray, speed: float = 1.0):
        self.id = id
        self.position = position.astype(float)
        self.speed = speed
        self.velocity = self._generate_random_direction() * self.speed

    def _generate_random_direction(self) -> np.ndarray:
        """Generates a random 3D unit vector for the trajectory."""
        direction = np.random.randn(3)
        return direction / np.linalg.norm(direction)

    def update_position(self, dt: float):
        """Moves the point along its current velocity vector."""
        self.position += self.velocity * dt

    def set_new_trajectory(self):
        """Assigns a completely new random trajectory."""
        self.velocity = self._generate_random_direction() * self.speed


class PredictiveEngine:
    """Monitors trajectories and prevents points from crossing the proximity threshold."""

    def __init__(self, threshold: float, look_ahead_time: float = 2.0):
        self.threshold = threshold
        self.look_ahead_time = look_ahead_time

    def enforce_thresholds(self, points: List[Point3D], dt: float):
        """
        Checks all pairs of points. If a predicted future position brings them
        closer than the threshold, their trajectories are adjusted.
        """
        num_points = len(points)
        for i in range(num_points):
            for j in range(i + 1, num_points):
                p1, p2 = points[i], points[j]

                # Predict future positions based on current velocities
                future_pos1 = p1.position + (p1.velocity * self.look_ahead_time)
                future_pos2 = p2.position + (p2.velocity * self.look_ahead_time)

                # Calculate future distance
                future_distance = np.linalg.norm(future_pos1 - future_pos2)
                current_distance = np.linalg.norm(p1.position - p2.position)

                # If they are going to breach the threshold, or are already breaching it
                if future_distance < self.threshold or current_distance < self.threshold:
                    # Trajectory Adjustment Algorithm:
                    # Steer away from each other
                    repulsion_vector = p1.position - p2.position

                    # Normalize and apply to velocities
                    if np.linalg.norm(repulsion_vector) != 0:
                        repulsion_dir = repulsion_vector / np.linalg.norm(repulsion_vector)
                        p1.velocity = repulsion_dir * p1.speed
                        p2.velocity = -repulsion_dir * p2.speed


class SpaceEnvironment:
    """The main simulation space that ties points and the engine together."""

    def __init__(self, num_points: int, space_size: float, threshold: float):
        self.space_size = space_size
        self.points = []

        # Initialize points at random locations
        for i in range(num_points):
            pos = np.random.uniform(0, space_size, 3)
            self.points.append(Point3D(id=i, position=pos, speed=2.0))

        self.engine = PredictiveEngine(threshold=threshold)

    def step(self, dt: float = 0.1):
        """Advances the simulation by one time step."""
        # 1. Engine monitors and adjusts trajectories
        self.engine.enforce_thresholds(self.points, dt)

        # 2. Update positions and enforce outer boundary conditions
        for p in self.points:
            p.update_position(dt)
            self._enforce_boundaries(p)

    def _enforce_boundaries(self, point: Point3D):
        """Bounce points off the walls of the simulation space."""
        for axis in range(3):
            if point.position[axis] <= 0 or point.position[axis] >= self.space_size:
                point.velocity[axis] *= -1  # Reverse direction on this axis
                # Keep within bounds
                point.position[axis] = np.clip(point.position[axis], 0, self.space_size)


# --- Visualization ---
def run_simulation(num_points=15, space_size=50.0, threshold=5.0):
    env = SpaceEnvironment(num_points, space_size, threshold)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.set_xlim(0, space_size)
    ax.set_ylim(0, space_size)
    ax.set_zlim(0, space_size)
    ax.set_title("SpaceBuff: Predictive 3D Point Engine")

    scatter = ax.scatter([p.position[0] for p in env.points],
                         [p.position[1] for p in env.points],
                         [p.position[2] for p in env.points], c='blue', marker='o')

    def update(frame):
        env.step(dt=0.2)

        # Update scatter plot data
        xs = [p.position[0] for p in env.points]
        ys = [p.position[1] for p in env.points]
        zs = [p.position[2] for p in env.points]

        scatter._offsets3d = (xs, ys, zs)
        return scatter,

    ani = animation.FuncAnimation(fig, update, frames=200, interval=50, blit=False)
    plt.show()


if __name__ == "__main__":
    run_simulation()
