"""Single source of truth for project paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SKILLS_DIR = ROOT / "skills"
GOAL_PATH = ROOT / "config" / "goal.yaml"
