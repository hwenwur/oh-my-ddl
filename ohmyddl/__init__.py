__version__ = "0.1.3"
__author__ = "hwenwur"


from pathlib import Path


DATA_DIR = Path.home() / ".ohmyddl"
if not DATA_DIR.exists():
    DATA_DIR.mkdir()
