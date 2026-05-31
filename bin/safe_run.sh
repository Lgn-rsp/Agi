#!/bin/bash
# safe_run.sh — cgroup-bounded launcher for own_math experiments.
# Usage: safe_run.sh <name> <mem_gb> <cpu_pct> <command...>
# Example: safe_run.sh exp01 1.5 60 python3 /root/own_math/src/exp01.py
set -euo pipefail
if [[ $# -lt 4 ]]; then
  echo "Usage: $0 <name> <mem_gb> <cpu_pct> <command...>" >&2
  exit 2
fi
NAME="$1"; MEM_GB="$2"; CPU_PCT="$3"; shift 3
exec systemd-run --scope --collect --quiet \
  -p "MemoryMax=${MEM_GB}G" \
  -p "MemorySwapMax=0" \
  -p "CPUQuota=${CPU_PCT}%" \
  --unit="safe-${NAME}-$$" \
  "$@"
