#!/bin/bash
# Serveur ASGI de production (derrière nginx sur le port 80)
cd "$(dirname "$0")"
exec ../.venv/bin/daphne -b 127.0.0.1 -p 8000 home.asgi:application
