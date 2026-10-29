#!/usr/bin/env bash
# la125 recipe (qwen3.8-flash-next-fp4-abliterated.yaml, home Spark 2026-10-22) translated to a plain launch.
# Identical flags and env to home. io_uring is blocked on Vast: a patched loader in box/ (when the engine needs one)
# falls back to pread for the weight loader and the PLE disk table.
export VLLM_PLE_TABLE_MEMORY=disk
export B12X_DISK_BACKEND=io_uring
export CUTE_DSL_ARCH=sm_121a
export SAFETENSORS_FAST_GPU=1
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export VLLM_SSM_CONV_STATE_LAYOUT=DS
export VLLM_USE_AOT_COMPILE=1
export VLLM_USE_MEGA_AOT_ARTIFACT=1
export VLLM_USE_V2_MODEL_RUNNER=1
export B12X_POLICY_MODE=auto
export VLLM_MXFP8_LM_HEAD=1
export VLLM_B12X_MOE_FP4_LAYER_MAX_INPUT_SCALE=w13
export VLLM_B12X_MOE_FP4_FORCE_A16=1
export B12X_W4A16_A4_PREFILL=1
export VLLM_ENGINE_READY_TIMEOUT_S=3600
export TZ=Europe/Vienna
export HF_HUB_OFFLINE=1
exec vllm serve /root/.cache/huggingface/local/Qwen3.8-Flash-Next-FP4-Local-abliterated \
  --served-model-name qwen \
  --host 0.0.0.0 \
  --port 8000 \
  --tensor-parallel-size 1 \
  --pipeline-parallel-size 1 \
  --mamba-cache-mode align \
  --enable-prefix-caching \
  --enable-chunked-prefill \
  --dtype bfloat16 \
  --kv-cache-dtype fp8 \
  --quantization modelopt_mixed \
  --block-size 16 \
  --load-format b12x \
  --max-model-len 262144 \
  --max-num-seqs 8 \
  --max-num-batched-tokens 2048 \
  --speculative-config '{"method":"mtp","num_speculative_tokens":4}' \
  --gdn-decode-kernel b12x \
  --linear-backend b12x \
  --moe-backend b12x \
  --no-enable-flashinfer-autotune \
  --mm-encoder-tp-mode data \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_xml \
  --enable-auto-tool-choice \
  --compilation-config '{"pass_config":{"fuse_act_quant":true}}' \
  --override-generation-config '{"temperature":1.0,"top_p":0.95,"top_k":20,"min_p":0.0,"presence_penalty":0.0,"repetition_penalty":1.0}' \
  --default-chat-template-kwargs '{"preserve_thinking": true}' \
  --gpu-memory-utilization 0.75
