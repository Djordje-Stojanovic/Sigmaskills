#!/usr/bin/env bash
# run_experiment.sh RUN_ID SERVE_SH [record]  - one full measured run on the box. Never edit after SETUP.
# Writes /root/runs/RUN_ID/{bw_before,bw_after,gate,speed,meta}.json, server.log, mem.log, then DONE.
set -u
ID=$1; SERVE=$2; MODE=${3:-}
BENCH=/root/work/bench; REF=/root/work/ref; OUT=/root/runs/$ID
mkdir -p "$OUT"; cd "$BENCH"
log() { echo "$(date -u +%FT%TZ) $*" | tee -a "$OUT/progress.log"; }
finish() { log "finish status=$1"; python3 - "$OUT" "$1" <<'EOF'
import json, sys, os
out, status = sys.argv[1], sys.argv[2]
meta = json.load(open(os.path.join(out, "meta.json"))) if os.path.exists(os.path.join(out, "meta.json")) else {}
meta["status"] = status
json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1)
EOF
  touch "$OUT/DONE"; exit 0; }
stop_server() { pkill -f "[v]llm serve" >/dev/null 2>&1; for i in $(seq 1 90); do pgrep -f "[v]llm serve" >/dev/null || break; sleep 2; done; pkill -9 -f "[v]llm serve" >/dev/null 2>&1; sleep 5; }

stop_server
cp "$SERVE" "$OUT/serve.sh"
python3 bw.py "$OUT/bw_before.json" >> "$OUT/progress.log" 2>&1 || log "bw_before failed"

# 1 s MemAvailable sampler for the whole start
( while [ ! -f "$OUT/.stopmem" ]; do echo "$(date +%s) $(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)" >> "$OUT/mem.log"; sleep 1; done ) &
T0=$(date +%s)
log "start server"
nohup bash "$OUT/serve.sh" > "$OUT/server.log" 2>&1 &
SPID=$!
until curl -sf http://localhost:8000/health >/dev/null; do
  sleep 3
  if ! kill -0 $SPID 2>/dev/null; then touch "$OUT/.stopmem"; tail -80 "$OUT/server.log" > "$OUT/died.log"; finish CRASH; fi
  if [ $(( $(date +%s) - T0 )) -gt 3600 ]; then touch "$OUT/.stopmem"; stop_server; finish TIMEOUT; fi
done
T1=$(date +%s); sleep 2; touch "$OUT/.stopmem"
LOW=$(awk 'NR==1 || $2<m {m=$2} END {print m}' "$OUT/mem.log")
KV=$(grep -oE "GPU KV cache size: [0-9,]+ tokens" "$OUT/server.log" | tail -1 | grep -oE "[0-9,]+" | tr -d ,)
python3 - "$OUT" "$((T1-T0))" "${LOW:-0}" "${KV:-0}" <<'EOF'
import json, sys, os
out, start_s, low, kv = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
json.dump({"start_s": start_s, "low_mem_gib": round(low / 1024, 2), "kv_tokens": kv}, open(os.path.join(out, "meta.json"), "w"), indent=1)
EOF
log "healthy after $((T1-T0)) s, low MemAvailable ${LOW} MiB, KV ${KV} tokens"
if [ "${LOW:-0}" -lt 4096 ]; then stop_server; finish MEMFLOOR; fi

# fixed warm-up: identical in every run (PLE pages, graphs, sampler)
python3 - <<'EOF'
from common import chat_stream, salt
for i in range(3):
    chat_stream([{"role": "user", "content": salt() + "Write 200 words about rivers."}], 256)
EOF
log "warm-up done"

if [ "$MODE" = record ]; then python3 gate.py --record "$REF" >> "$OUT/progress.log" 2>&1 || { stop_server; finish GATE_ERROR; }; fi
python3 gate.py --ref "$REF" --out "$OUT/gate.json" >> "$OUT/progress.log" 2>&1 || { stop_server; finish GATE_ERROR; }
log "gate done"
# ToolEvalBench quality + time (owner 2026-10-23): full suite (97 scenarios with --hardmode, tool-eval-bench main @c3d256a), no context fill (v4 fill took 24 min), real sampling, effort low, 8 parallel
TE0=$(date +%s)
tool-eval-bench run --base-url http://localhost:8000/v1 --model "${BENCH_MODEL:-qwen}" --hardmode \
  --temperature 1.0 --top-p 0.95 --top-k 20 --seed 42 --parallel 8 --no-live \
  --backend-kwargs '{"chat_template_kwargs": {"reasoning_effort": "low"}, "max_tokens": 65536}' \
  --json-file "$OUT/tooleval.json" > "$OUT/tooleval.log" 2>&1 || log "tooleval exited nonzero"
echo "{\"wall_s\": $(( $(date +%s) - TE0 ))}" > "$OUT/tooleval_time.json"
log "tooleval done in $(( $(date +%s) - TE0 )) s"
python3 speed.py --out "$OUT/speed.json" >> "$OUT/progress.log" 2>&1 || { stop_server; finish SPEED_ERROR; }
log "speed done"
# llama-benchy (forum-comparable numbers): only for the baseline and KEEP candidates (BENCHY=1)
if [ "${BENCHY:-1}" = 1 ]; then  # v4: every run
  llama-benchy --base-url http://localhost:8000/v1 --model "${BENCH_MODEL:-qwen}" \
    --tokenizer /root/.cache/huggingface/local/Qwen3.8-Flash-Next-FP4-Local-abliterated \
    --pp 2048 --tg 128 --depth 0 8192 32768 --concurrency 1 --runs 3 --no-cache --latency-mode generation \
    --save-result "$OUT/benchy.json" --format json > "$OUT/benchy.log" 2>&1 || log "benchy exited nonzero"
  log "benchy done"
fi
curl -s http://localhost:8000/metrics > "$OUT/metrics_end.txt"
stop_server
python3 bw.py "$OUT/bw_after.json" >> "$OUT/progress.log" 2>&1 || log "bw_after failed"
finish OK
