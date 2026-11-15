"""verify_weights.py EXPECTED.tsv - check every model file on the box against Hugging Face sizes and sha256.
LFS files are hashed (low priority, the server keeps running); small files are size-checked."""
import hashlib, os, sys

DIR = "/root/.cache/huggingface/local/Qwen3.8-Flash-Next-FP4-Local-abliterated"
os.nice(19)
bad = 0
for line in open(sys.argv[1], encoding="utf-8"):
    path, size, sha, src = line.rstrip("\n").split("\t")
    p = os.path.join(DIR, path)
    if not os.path.exists(p):
        print("MISSING", path); bad += 1; continue
    if os.path.getsize(p) != int(size):
        print("SIZE MISMATCH", path, os.path.getsize(p), size); bad += 1; continue
    if sha:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(64 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != sha:
            print("SHA MISMATCH", path, src); bad += 1; continue
    print("ok", src, path)
print("WEIGHTS", "IDENTICAL TO HF" if not bad else f"{bad} PROBLEM(S)")
