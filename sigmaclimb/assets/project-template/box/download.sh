#!/usr/bin/env bash
# download.sh - fetch la125 weights exactly as the home recipe describes. Log: /root/work/download.log
set -euo pipefail
export HF_TOKEN="$(cat /root/work/hf_token)"
export HF_HUB_ENABLE_HF_TRANSFER=1
DIR=/root/.cache/huggingface/local/Qwen3.8-Flash-Next-FP4-Local-abliterated
mkdir -p "$DIR"
date -u +"start %FT%TZ"
hf download nvidia/Qwen3.8-Flash-Next-FP4-Local --revision b9ce18a6887e18c089fdea8509a33e63429a3300 --local-dir "$DIR" \
  || HF_HUB_DISABLE_XET=1 hf download nvidia/Qwen3.8-Flash-Next-FP4-Local --revision b9ce18a6887e18c089fdea8509a33e63429a3300 --local-dir "$DIR"
date -u +"base done %FT%TZ"
# the Loke shards overwrite the 2 edited base shards
hf download Loke-60000/Qwen3.8-Flash-Next-FP4-Local-abliterated --local-dir "$DIR" \
  || HF_HUB_DISABLE_XET=1 hf download Loke-60000/Qwen3.8-Flash-Next-FP4-Local-abliterated --local-dir "$DIR"
date -u +"loke done %FT%TZ"
du -sh "$DIR"
find "$DIR" -name '*.safetensors' | wc -l
echo DOWNLOAD_DONE
