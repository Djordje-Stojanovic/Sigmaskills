"""pull_image_pkgs.py REPO TAG OUTDIR - unpack the Python packages of a Docker Hub image into OUTDIR (no Docker needed).

Downloads the arm64 image layers from registry-1.docker.io (anonymous pull token) and extracts only
usr/local/lib/python3.12/dist-packages/ and usr/local/bin/ into OUTDIR, applying OCI whiteouts.
Run vLLM from it with PYTHONPATH=OUTDIR/dist-packages (packages there win over the container's own).
"""
import gzip, io, json, os, shutil, sys, tarfile, urllib.request

REPO, TAG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
KEEP = ("usr/local/lib/python3.12/dist-packages/", "usr/local/bin/")
REG = "https://registry-1.docker.io/v2"


def token():
    u = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{REPO}:pull"
    return json.load(urllib.request.urlopen(u))["token"]


def get(path, tok, accept=None):
    req = urllib.request.Request(f"{REG}/{REPO}/{path}", headers={"Authorization": f"Bearer {tok}"})
    if accept:
        req.add_header("Accept", accept)
    return urllib.request.urlopen(req)


tok = token()
idx = json.load(get(f"manifests/{TAG}", tok, "application/vnd.oci.image.index.v1+json,"
                    "application/vnd.docker.distribution.manifest.list.v2+json,"
                    "application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.manifest.v1+json"))
if "manifests" in idx:  # multi-arch index -> pick arm64
    m = [x for x in idx["manifests"] if x.get("platform", {}).get("architecture") == "arm64"][0]
    idx = json.load(get(f"manifests/{m['digest']}", tok, m["mediaType"]))
layers = idx["layers"]
print(f"{len(layers)} layers, {sum(l['size'] for l in layers) / 2**30:.1f} GiB compressed", flush=True)

os.makedirs(OUT, exist_ok=True)
for i, layer in enumerate(layers, 1):
    tok = token()  # tokens expire after ~5 min
    blob = get(f"blobs/{layer['digest']}", tok)
    tmp = os.path.join(OUT, ".layer.tmp")
    with open(tmp, "wb") as fh:
        shutil.copyfileobj(blob, fh, 1 << 22)
    kept = 0
    with tarfile.open(tmp, "r:*") as tf:
        for mem in tf:
            name = mem.name.lstrip("./")
            if not name.startswith(KEEP):
                continue
            base = os.path.basename(name)
            target = os.path.join(OUT, name)
            if base.startswith(".wh."):  # whiteout: delete what an earlier layer added
                victim = os.path.join(os.path.dirname(target), base[4:])
                shutil.rmtree(victim, ignore_errors=True) if os.path.isdir(victim) else (
                    os.path.exists(victim) and os.remove(victim))
                continue
            if mem.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.lexists(target):
                os.remove(target) if not os.path.isdir(target) else shutil.rmtree(target)
            tf.extract(mem, OUT, set_attrs=False, filter="fully_trusted")
            kept += 1
    os.remove(tmp)
    print(f"layer {i}/{len(layers)}: {layer['size'] / 2**20:.0f} MiB, kept {kept} files", flush=True)
print("PULL_DONE", flush=True)
