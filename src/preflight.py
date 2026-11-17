"""Environment check: run `python -m src.preflight` before the pipeline.

Checks the Python version, required packages, the six raw CSVs (present, readable,
expected columns) and write access, and prints a fix for anything that fails.
"""
import importlib
import platform
import sys

from . import config as C

REQUIRED_FILES = {
    "ball_by_ball.csv": ["match_id", "innings", "innings_ball_num", "dismissal_type",
                         "extras_type", "is_four", "is_six", "is_wicket", "bowl_speed"],
    "matches.csv": ["match_id"],
    "competitions.csv": [],
    "teams.csv": [],
    "competition_team_player_mapping.csv": [],
    "playing_eleven.csv": [],
}
PACKAGES = ["pandas", "numpy", "scipy", "sklearn", "pyarrow", "streamlit", "plotly"]


def check(verbose=True):
    problems = []
    say = print if verbose else (lambda *a, **k: None)

    say(f"Python {platform.python_version()} on {platform.system()} {platform.release()}")
    if sys.version_info < (3, 10):
        problems.append("Python 3.10 or newer is needed (3.11-3.13 recommended).")

    for p in PACKAGES:
        try:
            m = importlib.import_module(p)
            say(f"  ok  {p:<10} {getattr(m, '__version__', '?')}")
        except Exception as e:  # noqa: BLE001
            problems.append(f"Package '{p}' missing or broken ({e.__class__.__name__}). "
                            f"Fix: python -m pip install -r requirements.txt")

    say(f"Project root: {C.ROOT}")
    say(f"Raw data:     {C.RAW}")
    if not C.RAW.exists():
        problems.append(f"Folder not found: {C.RAW}. Put the six supplied CSVs in data\\raw\\ "
                        f"inside the project folder (the folder that contains 'src').")
    else:
        import pandas as pd
        for name, cols in REQUIRED_FILES.items():
            f = C.RAW / name
            if not f.exists():
                alt = [x.name for x in C.RAW.iterdir() if x.name.lower().startswith(name.split(".")[0].lower())]
                hint = f" Found similar: {alt} - rename it to {name}." if alt else ""
                problems.append(f"Missing file: {f}.{hint}")
                continue
            size = f.stat().st_size
            if size < 1000:
                problems.append(f"{name} is only {size} bytes. It is probably a Git LFS pointer or a "
                                f"failed upload; copy the real file from the zip.")
                continue
            try:
                head = pd.read_csv(f, nrows=5)
            except Exception as e:  # noqa: BLE001
                problems.append(f"Cannot read {name}: {e}")
                continue
            miss = [c for c in cols if c not in head.columns]
            if miss:
                problems.append(f"{name} lacks columns {miss}. Columns found: {list(head.columns)[:12]}")
            say(f"  ok  {name:<38} {size / 1e6:6.1f} MB")

    for d in (C.OUT, C.PROCESSED):
        try:
            d.mkdir(parents=True, exist_ok=True)
            t = d / ".write_test"
            t.write_text("ok", encoding="utf-8")
            t.unlink()
        except Exception as e:  # noqa: BLE001
            problems.append(f"Cannot write to {d}: {e}. Close Excel/Explorer windows using it, "
                            f"or move the project out of OneDrive.")

    if problems:
        say("\nPROBLEMS FOUND:")
        for p in problems:
            say(f"  - {p}")
    else:
        say("\nAll checks passed. Run: python -m src.pipeline")
    return problems


if __name__ == "__main__":
    sys.exit(1 if check() else 0)
