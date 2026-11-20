"""Topology-preserving contour export and elementary geometric measurements.

Native coordinates are micrometres, x horizontal and y up. No display smoothing
or synthetic roughness is added. All closed contours are retained as holes.
"""
from __future__ import annotations
import math


def ordered_paths(nodes, lines):
    adjacency = {}
    for i, (a, b) in enumerate(lines):
        adjacency.setdefault(a, []).append((i, b))
        adjacency.setdefault(b, []).append((i, a))
    remaining = set(range(len(lines)))
    paths = []
    while remaining:
        edge = min(remaining)
        a, b = lines[edge]
        # Find an endpoint in this connected component, if there is one.
        stack, seen = [a], set()
        start = a
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            if len(adjacency[node]) == 1:
                start = node
                break
            stack.extend(other for _, other in adjacency[node] if other not in seen)
        chain, current = [start], start
        while True:
            choices = [(i, other) for i, other in adjacency[current] if i in remaining]
            if not choices:
                break
            i, current = choices[0]
            remaining.remove(i)
            chain.append(current)
            if current == start:
                break
        paths.append([[float(nodes[i][0]) * 1000, float(nodes[i][1]) * 1000] for i in chain])
    return paths


def intersections(paths, value, axis):
    """Intersect piecewise-linear contours, returning the other coordinate."""
    hits = []
    for path in paths:
        for a, b in zip(path, path[1:]):
            delta = b[axis] - a[axis]
            if abs(delta) < 1e-12:
                continue
            t = (value - a[axis]) / delta
            if -1e-10 <= t <= 1 + 1e-10:
                hits.append(a[1-axis] + t * (b[1-axis] - a[1-axis]))
    return sorted(set(round(v, 9) for v in hits))


def gap_at(paths, y):
    hits = intersections(paths, y, 1)
    left, right = [v for v in hits if v < 0], [v for v in hits if v >= 0]
    return min(right) - max(left) if left and right else 0.0


def measurements(layers, model, params):
    outer = layers[-1]["paths_nm"]
    floor_hits = intersections(outer, 0, 0)
    surface_y = max(floor_hits) if floor_hits else None
    if surface_y is None:
        raise ValueError("No top-visible centre surface in exported mesh")
    depth = max(0, -surface_y)
    top_hits = intersections(outer, params["pitch_nm"] * .4, 0)
    top = max(top_hits) if top_hits else 0
    if model == "etch":
        mid_width = gap_at(outer, -depth * .5) if depth > params["grid_nm"] else 0
        return {"center_depth_nm": depth, "width_half_depth_nm": mid_width,
                "mask_loss_nm": max(0, params["mask_nm"] - top)}
    # Measure coating against the retained Si interface, including a preceding
    # etch/strip result. A fabricated rectangular depth would erase its history.
    substrate = layers[0]["paths_nm"]
    base_floor = max(intersections(substrate, 0, 0))
    base_top = max(intersections(substrate, params["pitch_nm"] * .4, 0))
    top_film, bottom = max(0, top - base_top), max(0, surface_y - base_floor)
    resolved = base_top - base_floor > 2 * params["grid_nm"]
    width = gap_at(outer, (base_top + base_floor) * .5) if resolved else None
    minimum = min(gap_at(outer, base_top + (base_floor-base_top) * i / 20)
                  for i in range(1, 19)) if resolved else None
    return {"top_film_nm": top_film, "bottom_film_nm": bottom,
            "bottom_top_pct": 100 * bottom / top_film if top_film > 1e-6 else 0,
            "mid_gap_nm": width, "minimum_gap_nm": minimum}
