#!/usr/bin/env bash
# download.sh - fetch the weights named in box/model.env exactly as the owner's recipe describes. Log: /root/work/download.log
set -euo pipefail
. "$(dirname "$0")/model.env"
for v in MODEL_ID MODEL_REVISION MODEL_DIR SERVED_NAME; do
  case "${!v:-<}" in *"<"*) echo "set $v in box/model.env" >&2; exit 2;; esac
done
export HF_TOKEN="${HF_TOKEN:-$(cat /root/work/hf_token)}"
export HF_HUB_ENABLE_HF_TRANSFER=1
DIR="$MODEL_DIR"
mkdir -p "$DIR"
date -u +"start %FT%TZ"
hf download "$MODEL_ID" --revision "$MODEL_REVISION" --local-dir "$DIR" \
  || HF_HUB_DISABLE_XET=1 hf download "$MODEL_ID" --revision "$MODEL_REVISION" --local-dir "$DIR"
date -u +"base done %FT%TZ"
if [ -n "${OVERLAY_ID:-}" ]; then
  # the overlay shards overwrite the edited base shards
  hf download "$OVERLAY_ID" --local-dir "$DIR" \
    || HF_HUB_DISABLE_XET=1 hf download "$OVERLAY_ID" --local-dir "$DIR"
  date -u +"overlay done %FT%TZ"
fi
du -sh "$DIR"
find "$DIR" -name '*.safetensors' | wc -l
echo DOWNLOAD_DONE
