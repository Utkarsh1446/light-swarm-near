"""Global colour-map bidder.

Fits one input colour to one output colour on aligned cells. Abstains on an
identity map or a shape change. Unseen colours are copied. This is the
over-confident specialist: it is right on global recolour and wrong when only
the largest object changes.
"""

from __future__ import annotations

from swarm.dsl import shape

Map = dict[int, int]


def infer_map(demos: list[tuple[list[list[int]], list[list[int]]]]) -> Map | None:
    mapping: dict[int, int] = {}
    for grid_in, grid_out in demos:
        if shape(grid_in) != shape(grid_out):
            return None
        height, width = shape(grid_in)
        for row in range(height):
            for col in range(width):
                src = grid_in[row][col]
                dst = grid_out[row][col]
                if src in mapping and mapping[src] != dst:
                    return None
                mapping[src] = dst
    if not mapping or all(src == dst for src, dst in mapping.items()):
        return None
    return mapping


def apply_map(grid: list[list[int]], mapping: Map) -> list[list[int]]:
    return [[mapping.get(value, value) for value in row] for row in grid]
