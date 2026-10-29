#!/bin/zsh
# Abre el asistente en Terminal.app, que es quien recibe el permiso de micrófono.
cd "$(dirname "$0")/.." || exit 1
exec /opt/homebrew/bin/uv run asistente
