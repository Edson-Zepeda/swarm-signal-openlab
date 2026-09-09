"""SWARM SIGNAL: measured WiFi, traceable evidence."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor' / 'ruview'))
__version__ = '1.0.0'
