# Vast.ai setup: account, CLI, rent, use the box

Verified 2026-10-22 to 10-26 with vastai CLI 1.9.0 on Windows 11 and PowerShell. This file replaces the old `vast.md`.

## 1. Where things live (per project)

| Thing | Path | Rule |
|---|---|---|
| Vast API key | `<project>/secrets/vast_api_key` (no newline) | Never print it, never commit it |
| HF token | `<project>/secrets/hf_token` | Same. Push to the box as `/root/work/hf_token`, mode 600 |
| SSH known_hosts | `<project>/secrets/vast_known_hosts` | Disposable boxes only |
| vastai CLI | `vastai` from pip; on Windows often only in your Python's `Scripts` folder | Install: `python -m pip install --upgrade vastai`. Find it with `where vastai` or `command -v vastai` |
| Vast docs copy | `<project>/reference/vast_docs/llms-full.txt` | Grep it. Source: `https://docs.vast.ai/llms-full.txt` (~1.5 MB) |
| Instance record | `<project>/state.tmp/instance.json`, later `state/instance.json` | id, dph, image, ssh_host, ssh_port, rented_utc |

Reuse one key. A Vast API key does not expire, so the owner creates it once and keeps it in one key store (a
password manager or a git-ignored keys file, as `VAST_API_KEY`). Each new project copies it from there into
`secrets/vast_api_key`, and each machine runs `vastai set api-key` once. Ask the owner where the store is; never
create a new key for a new project. Never put a key into this skill's folder.

## 2. Login and the 2FA flow

```powershell
$v = (Get-Command vastai).Source        # or the full path to vastai.exe
& $v set api-key (Get-Content <project>\secrets\vast_api_key -Raw).Trim()   # once; never echo the value
& $v tfa send-email                      # prints a secret token; Vast emails a 6-digit code to the owner
& $v tfa login --method-type email --secret <SECRET> -c <CODE>   # owner types the digits in chat
```

- Vast needs a 2FA session even if no 2FA method was ever set up. Without it: "requires ... Two Factor
  Authentication".
- The session lasts about 25 hours. On expiry, SSH and running jobs keep working; only account calls fail
  (credit, `show instances`, `status.py`). Repeat the flow; write "NEED VAST EMAIL CODE" at the top of
  `PROGRESS.md` and in the turn output while you wait.
- **Never pass `--api-key` on later calls.** It bypasses the session and returns 401.
- `status.py` must treat any non-list answer as "cannot reach Vast", never as "instance gone".
- Credit: `& $v show user --raw` -> `credit`. Auto top-up (if on) is set by the owner only.

## 3. CLI quirks

- Use `show instances --raw`. `show instance <id>` is denied for this key.
- `destroy instance <id> -y` needs `-y`. Only the owner decides to destroy the working box.
- `search offers 'gpu_name=GB10'` returns 0. Use `cpu_arch=arm64` for GB10 / DGX Spark.
- SSH key: `& $v create ssh-key (Get-Content ~\.ssh\id_ed25519.pub -Raw).Trim()`; list with `show ssh-keys --raw`.

## 4. Search and rent

```powershell
& $v search offers 'cpu_arch=arm64 rentable=true reliability>=0.98 disk_space>=350 inet_down>=500' -o 'dph' --raw
& $v create instance <OFFER_ID> --image <serving-image:tag> --disk 350 --ssh --direct --label <name> --raw
```

Filters that matter:
- `reliability>=0.98` (not a flaky host), `disk_space>=<weights + 2 x cache + 50 GB>`, `inet_down>=500` (Mbps, for
  weights), `rentable=true`, `dph` sort (price per hour; disk is billed separately and small).
- Other GPUs: `gpu_name=H100_SXM num_gpus=1`, `RTX_5090`, etc. Check the exact names with a broad search first.
- Seen GB10 prices: $0.28-0.42/h. Cost of a 40-minute experiment: about $0.20.

Rent rules:
- Rent ONE instance. Never a second one.
- `success:false`, or "loading" with intended "stopped" for 3 minutes ("resources currently unavailable"):
  `destroy -y` and take the next offer.
- The instance image IS the serving image (no Docker inside). If it cannot boot with SSH, rent a CUDA base
  image and install the engine build inside. Log the ruling.
- Poll with `show instances --raw`. An 18 GB image pulls in about 4 minutes.
- Do a 5-minute test rental first on a cheap image: SSH, `nvidia-smi`, io_uring probe, HF speed, destroy.
- Security options (`seccomp=unconfined`, privileged) may be refused by the safety classifier. Use code fallbacks.

## 5. The box.ps1 / launch.ps1 / wait.ps1 pattern

All three read the instance file and `secrets/vast_known_hosts`.

```powershell
.\scripts\box.ps1 'nvidia-smi; df -h /; free -g'                         # remote command
.\scripts\box.ps1 -Push -Src local\file -Dst /root/work/x                # copy up (recursive)
.\scripts\box.ps1 -Pull -Src /root/runs/0005/. -Dst runs\0005\raw        # copy down
.\scripts\launch.ps1 -Run 0005 -Serve candidate\serve.sh [-Record] [-NoBenchy]   # invariants, push, start; returns at once
.\scripts\wait.ps1 -Run 0005 -MaxMinutes 90                              # run in the background; retries; pulls raw files
```

- Do pushes and pulls from PowerShell. Git Bash rewrites `/root/...` paths in `scp`.
- Use named `-Src/-Dst` parameters (a `[string[]]` param swallowed paths once).
- Windows shell files have CRLF: `launch.ps1` runs `sed -i 's/\r$//'` after the push.
- Long jobs: `(nohup bash job.sh > log 2>&1 &)` on the box, then a background `wait.ps1` locally. It prints one line
  per stage change and `RUN <id> FINISHED ...`. Every SSH call inside it is retried.
- Put Python in files, push them, run them. Do not quote Python through PowerShell, ssh and bash.
- `pkill -f "[v]llm serve"` (the bracket stops the pattern matching its own ssh command).
- Never edit a bash script while it runs. Write a versioned copy.
- The box clock is UTC. Print `date -u` next to local time in status answers.

## 6. Container limits found on a GB10 box

| Thing | Result |
|---|---|
| Kernel / driver | same as the owner's DGX Spark (7.0.0-1019-nvidia, 580.178.04) |
| RAM / cores | 121 GiB unified, 20 cores, aarch64 |
| Docker inside | no |
| io_uring | blocked (seccomp, EPERM) -> use a `pread` fallback |
| GPUDirect Storage (cuFile) | fails (error 5027) |
| Drop page cache, host sysctl, GPU clocks | not possible (no host root) |
| HF download | 80-230 MB/s (96 GB in 8-20 min); `HF_HUB_DISABLE_XET=1` if xet answers 416 |
| Read-only memory bandwidth | 238-240 GB/s of 273 advertised |

io_uring probe: `python3 -c "import ctypes;l=ctypes.CDLL(None,use_errno=True);print(l.syscall(425,8,ctypes.create_string_buffer(120)), ctypes.get_errno())"` (-1 and errno 1 = blocked).

## 7. Weights

Download in the background, then verify every file's sha256 against Hugging Face (tree API `lfs.oid`). For an
overlay repo on top of a base, check the overlay's commit history. Keep `~/.cache` of the engine and kernel
caches on the box (persistent) so restarts take 5 minutes, not 15.

## 8. Costs and ending

24 hours of box time is about $7-9. The biggest waste was an idle night after a dead watcher (~$2.40).
Only the owner destroys the instance (web UI, or `destroy instance <id> -y` on their word). `status.py` prints
`LOOP FINISHED: instance <id> destroyed by owner, REPORT.md written` only when the instance is gone and
`REPORT.md` exists. That line ends the host's long run.
