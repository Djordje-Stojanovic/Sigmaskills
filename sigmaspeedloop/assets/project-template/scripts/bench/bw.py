"""bw.py - GB10 memory bandwidth probe (~10 s). Run only while no server holds the GPU.
GB10 bandwidth can flip between ~70 and ~225 GB/s; a run with a flip is re-run, never judged."""
import json, sys, time

import torch

n = 512 * 1024 * 1024  # 1 GiB of fp16 per buffer (2 bytes x 512M)
a = torch.empty(n, dtype=torch.float16, device="cuda")
b = torch.empty(n, dtype=torch.float16, device="cuda")
a.fill_(1.0)
torch.cuda.synchronize()
for _ in range(3):
    b.copy_(a)
torch.cuda.synchronize()
reps, t0 = 20, time.perf_counter()
for _ in range(reps):
    b.copy_(a)
torch.cuda.synchronize()
dt = time.perf_counter() - t0
gbps = reps * 2 * a.numel() * a.element_size() / dt / 1e9  # read + write
out = {"copy_gbps": round(gbps, 1), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
json.dump(out, open(sys.argv[1], "w")) if len(sys.argv) > 1 else None
print(json.dumps(out))
