#!/usr/bin/env bash
# target.sh - the serving example's steps, called by run_experiment.sh on the box. Another target: replace this file.
#   start SERVE_SH OUT | warmup OUT | score OUT | quality OUT | stop OUT
# RECORD=1 makes the quality step record the gate's references (baseline run). BENCHY=1 adds llama-benchy to score.
set -u
CMD=$1; shift
BENCH=$(cd "$(dirname "$0")" && pwd); REF=${REF:-$CLIMB_ROOT/ref}
cd "$BENCH"
stop_server() { pkill -f "[v]llm serve" >/dev/null 2>&1; for i in $(seq 1 90); do pgrep -f "[v]llm serve" >/dev/null || break; sleep 2; done; pkill -9 -f "[v]llm serve" >/dev/null 2>&1; sleep 5; }

case "$CMD" in
start)
  SERVE=$1; OUT=$2
  stop_server
  python3 bw.py "$OUT/bw_before.json" || echo "bw_before failed"
  ( while [ ! -f "$OUT/.stopmem" ]; do echo "$(date +%s) $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)" >> "$OUT/mem.log"; sleep 1; done ) &
  T0=$(date +%s)
  nohup bash "$SERVE" > "$OUT/server.log" 2>&1 &
  SPID=$!
  until curl -sf http://localhost:8000/health >/dev/null; do
    sleep 3
    if ! kill -0 $SPID 2>/dev/null; then touch "$OUT/.stopmem"; tail -80 "$OUT/server.log" > "$OUT/died.log"; exit 1; fi
    if [ $(( $(date +%s) - T0 )) -gt 3600 ]; then touch "$OUT/.stopmem"; echo "TIMEOUT" > "$OUT/status"; exit 1; fi
  done
  T1=$(date +%s); sleep 2; touch "$OUT/.stopmem"
  LOW=$(awk 'NR==1 || $2<m {m=$2} END {print m}' "$OUT/mem.log")
  KV=$(grep -oE "GPU KV cache size: [0-9,]+ tokens" "$OUT/server.log" | tail -1 | grep -oE "[0-9,]+" | tr -d ,)
  echo "{\"start_s\": $((T1-T0)), \"low_mem_mib\": ${LOW:-0}, \"kv_tokens\": ${KV:-0}}" > "$OUT/start.json"
  if [ "${LOW:-0}" -lt 4096 ]; then echo "VOID: free memory fell to ${LOW} MiB during start (floor 4096)" > "$OUT/status"; exit 1; fi
  ;;
warmup)  # fixed and identical for champion and candidate: compiled graphs, pages and sampler warm, never cleared
  python3 - <<'EOF'
from common import chat_stream, salt
for i in range(3):
    chat_stream([{"role": "user", "content": salt() + "Write 200 words about rivers."}], 256)
EOF
  ;;
score)
  OUT=$1
  python3 speed.py --out "$OUT/speed.json" || exit 1  # also writes OUT/score.json
  if [ "${BENCHY:-0}" = 1 ]; then  # forum-comparable numbers, for the baseline and the final champion
    llama-benchy --base-url http://localhost:8000/v1 --model "${BENCH_MODEL:-qwen}" --tokenizer "${BENCH_TOKENIZER:?set BENCH_TOKENIZER}" \
      --pp 2048 --tg 128 --depth 0 8192 32768 --concurrency 1 --runs 3 --no-cache --latency-mode generation \
      --save-result "$OUT/benchy.json" --format json > "$OUT/benchy.log" 2>&1 || echo "benchy exited nonzero"
  fi
  ;;
quality)
  OUT=$1
  if [ "${RECORD:-0}" = 1 ]; then python3 gate.py --record "$REF" || exit 1; fi
  python3 gate.py --ref "$REF" --out "$OUT/gate.json" || exit 1
  # ToolEvalBench: full suite, real sampling, effort low, 8 parallel, no context fill
  tool-eval-bench run --base-url http://localhost:8000/v1 --model "${BENCH_MODEL:-qwen}" --hardmode \
    --temperature 1.0 --top-p 0.95 --top-k 20 --seed 42 --parallel 8 --no-live \
    --backend-kwargs '{"chat_template_kwargs": {"reasoning_effort": "low"}, "max_tokens": 65536}' \
    --json-file "$OUT/tooleval.json" > "$OUT/tooleval.log" 2>&1 || echo "tooleval exited nonzero"
  python3 quality.py "$OUT"
  ;;
stop)
  OUT=$1
  curl -s http://localhost:8000/metrics > "$OUT/metrics_end.txt"
  stop_server
  python3 bw.py "$OUT/bw_after.json" || echo "bw_after failed"
  ;;
*) echo "unknown step $CMD"; exit 2 ;;
esac
