#!/usr/bin/env bash
# run_experiment.sh RUN CHANGE [full] - one pass in two stages. Never edit it after the lock.
#   Stage 1 measures every score probe, then verdict.py decides. Anything but STAGE1-WIN ends the pass there.
#   Stage 2 runs the quality check on the same running target. "full" runs both stages (baseline and A/A runs).
# The target's own steps live in one script, TARGET (default scripts/bench/target.sh, the serving example):
#   start CHANGE OUT | warmup OUT | score OUT | quality OUT | stop OUT
#   score writes OUT/score.json, quality writes OUT/quality.json, a VOID reason goes to OUT/status.
# Writes RUN/raw/: change, meta.json (status + seconds per stage), progress.log, the target's files, then DONE.
set -u
RUN=$(printf '%s' "${1%/}" | tr '\134' /); CHANGE=$2; MODE=${3:-}  # a Windows path with backslashes works too
HERE=$(cd "$(dirname "$0")" && pwd)
export CLIMB_ROOT=${CLIMB_ROOT:-$(cd "$HERE/../.." && pwd)}
TARGET=${TARGET:-$HERE/target.sh}
PY=${PYTHON:-python3}
case "$RUN" in /*|[A-Za-z]:*) OUT=$RUN/raw ;; *) OUT=$CLIMB_ROOT/$RUN/raw ;; esac  # absolute: a box's /root/runs/<id>
rm -rf "$OUT"; mkdir -p "$OUT"; cp "$CHANGE" "$OUT/change"
STAGES=""

log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/progress.log"; }
step() {  # step NAME [ARG]: one target step, timed
  local t0 rc; t0=$(date +%s)
  bash "$TARGET" "$@" "$OUT" >> "$OUT/progress.log" 2>&1; rc=$?
  STAGES="$STAGES $1=$(( $(date +%s) - t0 ))"; log "$1 rc=$rc"; return $rc
}
meta() {
  "$PY" - "$OUT" "$1" $STAGES <<'EOF'
import json, os, sys
out, status = sys.argv[1], sys.argv[2]
stages = {k: int(v) for k, v in (x.split("=") for x in sys.argv[3:])}
json.dump({"status": status, "stage_s": stages}, open(os.path.join(out, "meta.json"), "w"), indent=1)
EOF
}
finish() { step stop; meta "$(cat "$OUT/status" 2>/dev/null || echo "$1")"; touch "$OUT/DONE"; exit 0; }

step start "$CHANGE" || finish CRASH
step warmup || finish CRASH
step score || finish SCORE_ERROR
if [ "$MODE" != full ]; then
  meta OK
  V=$(cd "$CLIMB_ROOT" && "$PY" "$HERE/verdict.py" "$RUN" | tail -1)
  log "stage 1: $V"
  case "$V" in "VERDICT STAGE1-WIN"*) ;; *) finish OK ;; esac
fi
step quality || finish QUALITY_ERROR
finish OK
