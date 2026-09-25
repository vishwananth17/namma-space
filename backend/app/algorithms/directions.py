"""Turn-by-Turn Natural Language Spatial Directions Engine.
Generates human-like navigation instructions with compass headings,
angular turn classification, and nearby landmark contextual cues.
"""

import math
from typing import List, Optional
from app.models.common import Point3D
from app.models.navigation import DirectionStep
from app.models.poi import POIResponse


CARDINAL_DIRECTIONS = [
    ("N", 0, 22.5),
    ("NE", 22.5, 67.5),
    ("E", 67.5, 112.5),
    ("SE", 112.5, 157.5),
    ("S", 157.5, 202.5),
    ("SW", 202.5, 247.5),
    ("W", 247.5, 292.5),
    ("NW", 292.5, 337.5),
    ("N", 337.5, 360.0),
]


def bearing_to_cardinal(deg: float) -> str:
    """Map compass bearing (0-360 deg) to 8-point cardinal direction."""
    norm = deg % 360.0
    for card, low, high in CARDINAL_DIRECTIONS:
        if low <= norm < high:
            return card
    return "N"


def calculate_bearing(p1: Point3D, p2: Point3D) -> float:
    """Calculate compass bearing in degrees from p1 to p2.
    In Three.js right-handed system:
    +X is East (90 deg), -X is West (270 deg)
    -Z is North (0 deg), +Z is South (180 deg)
    """
    dx = p2.x - p1.x
    dz = p2.z - p1.z
    # Angle where -Z is 0 deg (North), +X is 90 deg (East)
    rad = math.atan2(dx, -dz)
    deg = math.degrees(rad)
    return (deg + 360.0) % 360.0


def calculate_turn_angle(v1: Point3D, v2: Point3D) -> float:
    """Calculate signed angle in degrees between two 2D vectors in the XZ plane.
    Positive -> turn right (clockwise). Negative -> turn left (counter-clockwise).
    """
    # 2D cross product: dx1 * dz2 - dz1 * dx2
    cross = v1.x * v2.z - v1.z * v2.x
    # 2D dot product: dx1 * dx2 + dz1 * dz2
    dot = v1.x * v2.x + v1.z * v2.z
    rad = math.atan2(cross, dot)
    return math.degrees(rad)


def classify_turn(turn_deg: float) -> str:
    """Classify angular turn into human turn descriptions."""
    if abs(turn_deg) < 18.0:
        return "STRAIGHT"
    elif 18.0 <= turn_deg < 50.0:
        return "SLIGHT_RIGHT"
    elif -50.0 < turn_deg <= -18.0:
        return "SLIGHT_LEFT"
    elif 50.0 <= turn_deg < 130.0:
        return "TURN_RIGHT"
    elif -130.0 < turn_deg <= -50.0:
        return "TURN_LEFT"
    elif turn_deg >= 130.0:
        return "SHARP_RIGHT"
    else:
        return "SHARP_LEFT"


def find_nearest_landmark(
    point: Point3D,
    pois: List[POIResponse],
    max_radius: float = 3.0,
    exclude_names: Optional[List[str]] = None,
) -> Optional[str]:
    """Find nearby POI to use as a navigational reference landmark."""
    exclude = set(exclude_names or [])
    best_name = None
    min_dist = max_radius

    for poi in pois:
        if poi.name in exclude:
            continue
        dist = math.hypot(poi.position.x - point.x, poi.position.z - point.z)
        if dist < min_dist:
            min_dist = dist
            best_name = poi.name

    return best_name


def generate_natural_directions(
    waypoints: List[Point3D],
    origin_name: str,
    destination_name: str,
    venue_pois: Optional[List[POIResponse]] = None,
) -> List[DirectionStep]:
    """Synthesizes step-by-step human-readable navigation directions from 3D waypoints."""
    if not waypoints or len(waypoints) < 2:
        return [
            DirectionStep(
                step=1,
                action="ARRIVE",
                instruction=f"You are already at {destination_name}.",
                distance_meters=0.0,
                compass_bearing_deg=0,
                cardinal_direction="N",
                nearby_landmark=None,
                waypoint_index=0,
            )
        ]

    steps: List[DirectionStep] = []
    pois = venue_pois or []
    step_num = 1

    # Leg vectors between waypoints
    vectors: List[Point3D] = []
    distances: List[float] = []
    bearings: List[float] = []

    for i in range(len(waypoints) - 1):
        p1 = waypoints[i]
        p2 = waypoints[i + 1]
        dx = p2.x - p1.x
        dz = p2.z - p1.z
        dist = math.hypot(dx, dz)
        vectors.append(Point3D(x=dx, y=0.0, z=dz))
        distances.append(round(dist, 1))
        bearings.append(calculate_bearing(p1, p2))

    # 1. First step: Departure
    initial_bearing = bearings[0]
    initial_cardinal = bearing_to_cardinal(initial_bearing)
    initial_dist = distances[0]
    start_landmark = find_nearest_landmark(
        waypoints[0], pois, max_radius=3.5, exclude_names=[destination_name]
    )

    landmark_phrase = f" near {start_landmark}" if start_landmark and start_landmark != origin_name else ""
    steps.append(
        DirectionStep(
            step=step_num,
            action="START",
            instruction=f"Depart from {origin_name}{landmark_phrase}, heading {initial_cardinal} for {initial_dist}m.",
            distance_meters=initial_dist,
            compass_bearing_deg=int(round(initial_bearing)),
            cardinal_direction=initial_cardinal,
            nearby_landmark=start_landmark,
            waypoint_index=0,
        )
    )
    step_num += 1

    # 2. Intermediate Waypoint Turns
    for i in range(1, len(vectors)):
        v_prev = vectors[i - 1]
        v_curr = vectors[i]
        turn_angle = calculate_turn_angle(v_prev, v_curr)
        action = classify_turn(turn_angle)
        leg_dist = distances[i]
        leg_bearing = bearings[i]
        leg_cardinal = bearing_to_cardinal(leg_bearing)

        # Landmark at turn junction
        turn_point = waypoints[i]
        landmark = find_nearest_landmark(
            turn_point, pois, max_radius=3.0, exclude_names=[origin_name, destination_name]
        )

        landmark_suffix = f" past {landmark}" if landmark else ""

        if action == "STRAIGHT":
            instruction = f"Continue straight{landmark_suffix} heading {leg_cardinal} for {leg_dist}m."
        elif action == "SLIGHT_RIGHT":
            instruction = f"Bear slight right{landmark_suffix} and proceed {leg_dist}m."
        elif action == "SLIGHT_LEFT":
            instruction = f"Bear slight left{landmark_suffix} and proceed {leg_dist}m."
        elif action == "TURN_RIGHT":
            instruction = f"Turn right{landmark_suffix} and walk {leg_dist}m."
        elif action == "TURN_LEFT":
            instruction = f"Turn left{landmark_suffix} and walk {leg_dist}m."
        elif action == "SHARP_RIGHT":
            instruction = f"Make a sharp right{landmark_suffix} and walk {leg_dist}m."
        else:
            instruction = f"Make a sharp left{landmark_suffix} and walk {leg_dist}m."

        steps.append(
            DirectionStep(
                step=step_num,
                action=action,
                instruction=instruction,
                distance_meters=leg_dist,
                compass_bearing_deg=int(round(leg_bearing)),
                cardinal_direction=leg_cardinal,
                nearby_landmark=landmark,
                waypoint_index=i,
            )
        )
        step_num += 1

    # 3. Final Step: Arrival
    steps.append(
        DirectionStep(
            step=step_num,
            action="ARRIVE",
            instruction=f"Arrive at {destination_name}.",
            distance_meters=0.0,
            compass_bearing_deg=int(round(bearings[-1])),
            cardinal_direction=bearing_to_cardinal(bearings[-1]),
            nearby_landmark=destination_name,
            waypoint_index=len(waypoints) - 1,
        )
    )

    return steps
