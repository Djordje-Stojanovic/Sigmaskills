# Engineering Kit pack setup

Source: [sybil-solutions/inference-optimisation-skill](https://github.com/sybil-solutions/inference-optimisation-skill) (`skills/`), pinned to one commit.

## Inference Optimisation

- **Python 3** (standard library only) for `scripts/bench.py` and `scripts/ceiling.py`.
- **Linux or macOS shell** (`bash`, `flock`) for `scripts/queue.sh` and `scripts/mem.sh`. `mem.sh` uses `docker` and either `nvidia-smi` (discrete NVIDIA GPUs) or `/proc/<pid>/fdinfo` (unified memory, which needs root or passwordless `sudo -n` to read another user's processes).
- **Keys and MCP servers:** none. `bench.py` talks only to the local OpenAI-compatible server URL you configure (`base_url`, default `http://127.0.0.1:8000`).
