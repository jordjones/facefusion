#!/bin/bash
set -u
cd "$(dirname "$0")"

export TMPDIR="$(pwd)/.temp"
mkdir -p "$TMPDIR" logs

export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1

LOG="logs/facefusion-$(date +%Y%m%d-%H%M%S).log"
echo "FaceFusion launch $(date) — log: $LOG"

source /opt/anaconda3/etc/profile.d/conda.sh
conda activate facefusion

( sleep 8 && open http://localhost:7860 ) &

trap '' HUP
exec caffeinate -dimsu uv run python -u facefusion.py run 2>&1 | tee "$LOG"
