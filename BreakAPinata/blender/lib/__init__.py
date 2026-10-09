"""Librería común de BREAK A PIÑATA (blender/lib).

Cada build.py hace:
    import sys, os
    sys.path.insert(0, <ruta a blender/>)
    from lib import geo, materials, palette, pipeline
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
