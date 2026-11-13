"""Parameter-free grid operations.

This is the 16-operation catalogue this repository runs. The broader design
uses a larger grid language. This file is not an ARC evaluator.
"""

from __future__ import annotations

Grid = list[list[int]]

GEO_OPS = ("rot90", "rot180", "rot270", "flip_h", "flip_v", "transpose")
COLOUR_OPS = ("cycle_fg", "fg_to_one", "invert_fg", "swap_top2")
OBJECT_OPS = (
    "crop_bbox",
    "keep_largest",
    "paint_largest",
    "gravity_down",
    "gravity_right",
    "tile2",
)
OP_NAMES = GEO_OPS + COLOUR_OPS + OBJECT_OPS
OP_INDEX = {name: index for index, name in enumerate(OP_NAMES)}
FAMILY_OF = {name: "geo" for name in GEO_OPS}
FAMILY_OF.update({name: "colour" for name in COLOUR_OPS})
FAMILY_OF.update({name: "object" for name in OBJECT_OPS})


def clone(grid: Grid) -> Grid:
    return [row[:] for row in grid]


def shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0])


def objects(grid: Grid) -> list[list[tuple[int, int]]]:
    height, width = shape(grid)
    seen = [[False] * width for _ in range(height)]
    found: list[list[tuple[int, int]]] = []
    for row in range(height):
        for col in range(width):
            if grid[row][col] == 0 or seen[row][col]:
                continue
            colour = grid[row][col]
            stack = [(row, col)]
            seen[row][col] = True
            cells: list[tuple[int, int]] = []
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if (
                        0 <= ny < height
                        and 0 <= nx < width
                        and not seen[ny][nx]
                        and grid[ny][nx] == colour
                    ):
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            found.append(cells)
    return found


def _best_object(grid: Grid) -> list[tuple[int, int]] | None:
    comps = objects(grid)
    if not comps:
        return None
    # Largest area, then the object whose top-left cell is earliest in scan order.
    return max(
        comps,
        key=lambda cells: (
            len(cells),
            -min(row for row, _ in cells),
            -min(col for _, col in cells),
        ),
    )


def rot90(grid: Grid) -> Grid:
    height, width = shape(grid)
    out = [[0] * height for _ in range(width)]
    for row in range(height):
        for col in range(width):
            out[col][height - 1 - row] = grid[row][col]
    return out


def rot180(grid: Grid) -> Grid:
    return rot90(rot90(grid))


def rot270(grid: Grid) -> Grid:
    return rot90(rot180(grid))


def flip_h(grid: Grid) -> Grid:
    return [list(reversed(row)) for row in grid]


def flip_v(grid: Grid) -> Grid:
    return [row[:] for row in reversed(grid)]


def transpose(grid: Grid) -> Grid:
    height, width = shape(grid)
    return [[grid[row][col] for row in range(height)] for col in range(width)]


def cycle_fg(grid: Grid) -> Grid:
    out = clone(grid)
    for row in out:
        for index, value in enumerate(row):
            if value != 0:
                row[index] = 1 if value == 9 else value + 1
    return out


def fg_to_one(grid: Grid) -> Grid:
    out = clone(grid)
    for row in out:
        for index, value in enumerate(row):
            if value != 0:
                row[index] = 1
    return out


def invert_fg(grid: Grid) -> Grid:
    out = clone(grid)
    for row in out:
        for index, value in enumerate(row):
            if value != 0:
                row[index] = 10 - value
    return out


def swap_top2(grid: Grid) -> Grid | None:
    counts: dict[int, int] = {}
    for row in grid:
        for value in row:
            if value:
                counts[value] = counts.get(value, 0) + 1
    if len(counts) < 2:
        return None
    ranking = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    left, right = ranking[0][0], ranking[1][0]
    out = clone(grid)
    for row in out:
        for index, value in enumerate(row):
            if value == left:
                row[index] = right
            elif value == right:
                row[index] = left
    return out


def crop_bbox(grid: Grid) -> Grid | None:
    height, width = shape(grid)
    cells = [(r, c) for r in range(height) for c in range(width) if grid[r][c]]
    if not cells:
        return None
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    return [row[c0 : c1 + 1] for row in grid[r0 : r1 + 1]]


def keep_largest(grid: Grid) -> Grid | None:
    best = _best_object(grid)
    if best is None:
        return None
    out = [[0] * len(grid[0]) for _ in range(len(grid))]
    for row, col in best:
        out[row][col] = grid[row][col]
    return out


def paint_largest(grid: Grid) -> Grid | None:
    best = _best_object(grid)
    if best is None:
        return None
    out = clone(grid)
    for row, col in best:
        out[row][col] = 1
    return out


def gravity_down(grid: Grid) -> Grid:
    height, width = shape(grid)
    out = [[0] * width for _ in range(height)]
    for col in range(width):
        values = [grid[row][col] for row in range(height) if grid[row][col]]
        for offset, value in enumerate(values):
            out[height - len(values) + offset][col] = value
    return out


def gravity_right(grid: Grid) -> Grid:
    height, width = shape(grid)
    out = [[0] * width for _ in range(height)]
    for row in range(height):
        values = [value for value in grid[row] if value]
        for offset, value in enumerate(values):
            out[row][width - len(values) + offset] = value
    return out


def tile2(grid: Grid) -> Grid | None:
    height, width = shape(grid)
    if height * 2 > 30 or width * 2 > 30:
        return None
    out = [[0] * (width * 2) for _ in range(height * 2)]
    for row in range(height):
        for col in range(width):
            value = grid[row][col]
            out[row][col] = value
            out[row][col + width] = value
            out[row + height][col] = value
            out[row + height][col + width] = value
    return out


OPS = {
    "rot90": rot90,
    "rot180": rot180,
    "rot270": rot270,
    "flip_h": flip_h,
    "flip_v": flip_v,
    "transpose": transpose,
    "cycle_fg": cycle_fg,
    "fg_to_one": fg_to_one,
    "invert_fg": invert_fg,
    "swap_top2": swap_top2,
    "crop_bbox": crop_bbox,
    "keep_largest": keep_largest,
    "paint_largest": paint_largest,
    "gravity_down": gravity_down,
    "gravity_right": gravity_right,
    "tile2": tile2,
}


def apply_op(grid: Grid, name: str) -> Grid | None:
    produced = OPS[name](grid)
    if produced is None:
        return None
    if len(produced) > 30 or len(produced[0]) > 30:
        return None
    return produced


def apply_program(grid: Grid, program: tuple[str, ...] | list[str]) -> Grid | None:
    current = grid
    for name in program:
        current = apply_op(current, name)
        if current is None:
            return None
    return current


def grids_equal(left: Grid | None, right: Grid | None) -> bool:
    return left is not None and left == right
