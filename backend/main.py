"""Vercel Services entrypoint for the RegimeShift FastAPI application."""

import sys
from importlib import import_module
from pathlib import Path

source_directory = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(source_directory))

app = import_module("regimeshift.main").app
