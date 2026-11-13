"""Program search over the small grid catalogue."""

from __future__ import annotations

from swarm.dsl import OP_NAMES, apply_program, grids_equal

Demo = tuple[list[list[int]], list[list[int]]]


def programs_in(ops: tuple[str, ...] | list[str], depth: int = 2) -> list[tuple[str, ...]]:
    singles = [(op,) for op in ops]
    if depth < 2:
        return singles
    pairs = [(left, right) for left in ops for right in ops]
    return singles + pairs


def fits_demos(program: tuple[str, ...], demos: list[Demo]) -> bool:
    for grid_in, grid_out in demos:
        if not grids_equal(apply_program(grid_in, program), grid_out):
            return False
    return True


def first_demo_fit(
    demos: list[Demo],
    programs: list[tuple[str, ...]],
) -> tuple[str, ...] | None:
    for program in programs:
        if fits_demos(program, demos):
            return program
    return None


def first_that_generalises(
    demos: list[Demo],
    test_in: list[list[int]],
    test_out: list[list[int]],
    ops: tuple[str, ...] | list[str],
) -> bool:
    """The first catalogue program that fits the demos also fits the test."""
    found = first_demo_fit(demos, programs_in(ops))
    if found is None:
        return False
    return grids_equal(apply_program(test_in, found), test_out)


def any_demo_fit(demos: list[Demo], ops: tuple[str, ...] | list[str]) -> bool:
    return first_demo_fit(demos, programs_in(ops)) is not None
