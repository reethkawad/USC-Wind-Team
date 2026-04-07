# conftest.py — makes pytest discover tests in this directory and adds project root to path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
