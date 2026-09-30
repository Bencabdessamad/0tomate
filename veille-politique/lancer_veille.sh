#!/usr/bin/env bash
# Lancement quotidien (cron). La clé peut être placée dans ~/.veille_env :
#   export ANTHROPIC_API_KEY=sk-ant-...
set -euo pipefail
cd "$(dirname "$0")"
[ -f "$HOME/.veille_env" ] && . "$HOME/.veille_env"
mkdir -p sorties
python3 veille.py --heures 24 --sortie excel >> sorties/planifie.log 2>&1
