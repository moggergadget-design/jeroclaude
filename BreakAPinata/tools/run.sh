#!/usr/bin/env bash
# Ejecuta un script de Blender sin interfaz con el módulo bpy del proyecto.
# Equivale a: blender --background --python <script>.py -- <argumentos>
# Uso: bash tools/run.sh blender/assets/lote_00/<id>/build.py --render all
set -euo pipefail
cd "$(dirname "$0")/.."
script="$1"; shift
exec .venv/bin/python "$script" -- "$@"
