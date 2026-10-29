"""Where the brain keeps its files: one folder of its own, so that it never meets another Aiwa installed beside it (the first Aiwa keeps its files in the home folder itself)."""
from pathlib import Path

DATA = Path.home() / ".aiwa_app"
DATA.mkdir(parents=True, exist_ok=True)
