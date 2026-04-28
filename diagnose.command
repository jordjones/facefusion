#!/bin/bash
cd "$(dirname "$0")"

echo "=== FaceFusion processes ==="
ps -ef | grep -E "facefusion|ffmpeg" | grep -v grep

echo
echo "=== Port 7860 ==="
lsof -ti:7860 || echo "(server not running)"

echo
echo "=== Latest log tail ==="
ls -t logs/*.log 2>/dev/null | head -1 | xargs -I{} tail -50 {}

echo
echo "=== Jetsam / OOM kills (last 2h) ==="
log show --last 2h --predicate 'eventMessage CONTAINS "jetsam" OR eventMessage CONTAINS "memorystatus"' 2>/dev/null | head -40

echo
echo "=== App Nap / power events (last 2h) ==="
log show --last 2h --predicate 'process == "powerd" OR eventMessage CONTAINS "App Nap"' 2>/dev/null | head -40

echo
echo "=== Disk space on TMPDIR ==="
df -h .temp 2>/dev/null
du -sh .temp/* 2>/dev/null | head -10
