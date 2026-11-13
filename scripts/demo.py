#!/usr/bin/env python3
"""Produce the screen-capturable demo artifacts.

Do: python scripts/demo.py
See: docs/media/dashboard.png, docs/media/frame_*.png, docs/media/dashboard.gif,
and a shot list printed to the terminal.

The script runs the seeded offline simulation, serves the dashboard, and, when
Chrome is installed, captures frames. It does not post anywhere and does not
touch mainnet.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swarm.sim import run_sim, write_outputs  # noqa: E402


FRAMES = (5, 10, 15, 20)
EXPLAINER_SHOTS = ("top", "agent", "subjects", "market-loop", "results", "experiment")


def main() -> None:
    report = run_sim(rounds=20, seed=1, quick=False)
    media = ROOT / "docs" / "media"
    media.mkdir(parents=True, exist_ok=True)
    write_outputs(report, media / "run.json", ROOT / "dashboard" / "data.js")
    headline = report["headline"]
    print("Solved", headline["solved"], "/", headline["posted"])
    print("Slashes", headline["slashes"], "subcontracts", headline["subcontracts"])
    print("Reputation", headline["final_reputation"])
    print("Shot list:")
    print("  1. Open the dashboard. The chart is reputation, starting at 1000.")
    print("  2. Round 5: mapfit is assigned the trap, slashed, object then solves.")
    print("  3. Round 10: a second slash. mapfit's score falls behind object.")
    print("  4. Round 15: object wins the trap on the first assignment. No slash.")
    print("  5. Round 16: curious solves a two-op task and pays a specialist 20%.")
    capture(media)
    print("Demo files are in docs/media/.")


def capture(media: Path) -> None:
    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if chrome is None:
        print("Chrome is not installed; screenshots were not captured.")
        return
    server = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1"],
        cwd=ROOT / "dashboard",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(0.6)
        for index, frame in enumerate(FRAMES, start=1):
            shot(chrome, f"http://127.0.0.1:8765/?frame={frame}", media / f"frame_{index:02d}.png")
        shot(chrome, "http://127.0.0.1:8765/?frame=20", media / "dashboard.png")
        for index, name in enumerate(EXPLAINER_SHOTS, start=1):
            shot(chrome, f"http://127.0.0.1:8765/?shot={name}", media / f"explainer_{index:02d}.png")
    finally:
        server.terminate()
        server.wait(timeout=5)
    if shutil.which("ffmpeg"):
        def gif(pattern: str, dest: Path) -> None:
            subprocess.check_call(
                [
                    "ffmpeg", "-y", "-framerate", "1", "-start_number", "1",
                    "-i", str(media / pattern),
                    "-vf", "scale=1000:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                    str(dest),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        gif("frame_%02d.png", media / "dashboard.gif")
        gif("explainer_%02d.png", media / "explainer.gif")


def shot(chrome: str, url: str, path: Path) -> None:
    # Chrome in this environment writes the PNG and then does not exit.
    # timeout keeps the capture finite; the screenshot is already on disk.
    subprocess.run(
        [
            "timeout", "20", chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", f"--user-data-dir=/tmp/chrome-shot-{path.stem}",
            "--window-size=1400,1100", "--hide-scrollbars", "--virtual-time-budget=4000",
            f"--screenshot={path}", url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if not path.exists() or path.stat().st_size < 1000:
        raise RuntimeError(f"screenshot missing: {path}")


if __name__ == "__main__":
    main()
