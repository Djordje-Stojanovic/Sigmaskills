"""cfgcheck.py SPEC_JSON - build the la125 VllmConfig without loading weights, print the failing assertion line."""
import json, sys, traceback

from vllm.engine.arg_utils import EngineArgs

args = EngineArgs(
    model="/root/.cache/huggingface/local/Qwen3.8-Flash-Next-FP4-Local-abliterated", served_model_name=["qwen"],
    max_model_len=262144, max_num_seqs=8, max_num_batched_tokens=4096, kv_cache_dtype="fp8",
    quantization="modelopt_mixed", dtype="bfloat16", block_size=16, load_format="b12x",
    enable_prefix_caching=True, enable_chunked_prefill=True, mamba_cache_mode="align",
    gpu_memory_utilization=0.75, speculative_config=json.loads(sys.argv[1]),
)
try:
    args.create_engine_config()
    print("CONFIG OK")
except Exception:
    tb = traceback.format_exc()
    lines = [l for l in tb.splitlines() if "vllm/" in l or "assert" in l.lower() or "Error" in l]
    print("\n".join(lines[-14:]))
