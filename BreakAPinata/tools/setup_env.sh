#!/usr/bin/env bash
# Recrea el entorno del proyecto (el contenedor es efímero).
# Uso: bash tools/setup_env.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if ! ldconfig -p | grep -q libEGL.so.1; then
  echo "Instalando Mesa EGL (necesario solo para EEVEE por software)…"
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libegl1 libegl-mesa0 libgl1-mesa-dri libgbm1
fi
[ -d .venv ] || uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python bpy==5.2.2 Pillow numpy
.venv/bin/python -c "import bpy; print('Blender', bpy.app.version_string)"
