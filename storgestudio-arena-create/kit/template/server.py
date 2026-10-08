"""blind-pairs arena server (pure stdlib). Blind: the page sees only random codes, never names or file names.

  python server.py               first free port in 3410-3499 (the arena range), opens nothing
  python server.py --port 3411   a fixed port
  python server.py --open        also opens the page in the browser

Files next to this script: arena.json (config + items), picks.jsonl (append-only), codes.json (blind codes),
results.json / results.md (rewritten on every board view). Media paths in arena.json are relative to this folder.
"""
import json, mimetypes, os, random, socket, string, sys, threading, time, uuid, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote, quote

import arena

HERE = arena.HERE
LOCK = threading.Lock()
KINDS = {".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".gif": "image", ".avif": "image",
         ".mp4": "video", ".webm": "video", ".mov": "video", ".mp3": "audio", ".wav": "audio", ".ogg": "audio",
         ".m4a": "audio", ".flac": "audio", ".txt": "text", ".md": "text", ".html": "html"}


def kind_of(it):
    if it.get("kind"):
        return it["kind"]
    if it.get("text") is not None:
        return "text"
    return KINDS.get(os.path.splitext(it.get("src", ""))[1].lower(), "image")


def codes(c):
    """One random code per item, kept across restarts (a new item gets a new code)."""
    k = arena.load("codes.json", {}) or {}
    used = set(k.values()); changed = False
    for it in c["items"]:
        if it["id"] not in k:
            while True:
                code = "".join(random.choice(string.ascii_uppercase) for _ in range(3))
                if code not in used:
                    break
            k[it["id"]] = code; used.add(code); changed = True
    if changed:
        arena.save("codes.json", k)
    return k, {v: i for i, v in k.items()}


def public_refs(g, gv):
    """A group's "refs": ["refs/a.jpg", {"src": "refs/b.wav", "label": "voice"}, ...] -> [{url, label, kind}] for the prompt bar."""
    out = []
    for i, r in enumerate(gv.get("refs") or []):
        src, label = (r.get("src", ""), r.get("label", "")) if isinstance(r, dict) else (r, "")
        out.append({"url": f"/g/{quote(g)}/{i}", "label": label, "kind": kind_of({"src": src})})
    return out


def public_item(it, code):
    k = kind_of(it)
    out = {"code": code, "kind": k}
    if k == "text":
        out["text"] = it["text"] if it.get("text") is not None else open(os.path.join(HERE, it["src"]), encoding="utf-8").read()
    else:
        out["url"] = f"/m/{code}"
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path).path
        c = arena.cfg()
        if p in ("/", "/index.html"):
            return self.send(200, open(os.path.join(HERE, "index.html"), "rb").read(), "text/html; charset=utf-8")
        if p == "/api/config":
            groups = {g: {"label": v.get("label", g), "prompt": v.get("prompt", ""), "retired": bool(v.get("retired"))} for g, v in c["groups"].items()}
            return self.send(200, {"title": c.get("title", "Arena"), "question": c.get("question", "Which one is better?"),
                                   "metrics": [{"id": m["id"], "label": m.get("label", m["id"]), "hint": m.get("hint", "")} for m in c["metrics"]],
                                   "groups": groups, "items": len(c["items"]), "players": len({i["player"] for i in c["items"]})})
        if p == "/api/next":
            with LOCK:
                ps = arena.picks()
                n = arena.next_pair(c, ps)
            if "error" in n:
                return self.send(200, n)
            k, _ = codes(c)
            items = {it["id"]: it for it in c["items"]}
            a, b = items[n["a"]], items[n["b"]]
            L, R = (a, b) if n["left"] == a["id"] else (b, a)
            g = a.get("group")
            gv = c["groups"].get(g, {})
            return self.send(200, {"token": uuid.uuid4().hex[:10], "left": public_item(L, k[L["id"]]), "right": public_item(R, k[R["id"]]),
                                   "group": {"id": g, "label": gv.get("label", g or ""), "prompt": gv.get("prompt", ""), "refs": public_refs(g, gv)},
                                   "repeat": bool(n.get("repeat_of")), "repeat_of": n.get("repeat_of"), "why": n["why"], "picks": len(ps)})
        if p == "/api/state":
            with LOCK:
                return self.send(200, arena.state(c))
        if p.startswith("/g/"):  # a group's reference media (the photos or voice the options must match): not a player, so not blind
            g, _, i = unquote(p[3:]).rpartition("/")
            refs = (c["groups"].get(g) or {}).get("refs") or []
            if not i.isdigit() or int(i) >= len(refs):
                return self.send(404, {"error": "unknown reference"})
            r = refs[int(i)]
            return self.file(os.path.join(HERE, r["src"] if isinstance(r, dict) else r))
        if p.startswith("/m/"):
            _, rev = codes(c)
            iid = rev.get(unquote(p[3:]))
            it = next((x for x in c["items"] if x["id"] == iid), None)
            if not it or not it.get("src"):
                return self.send(404, {"error": "unknown code"})
            return self.file(os.path.join(HERE, it["src"]))
        return self.send(404, {"error": "not found"})

    def file(self, path):
        """Serves media with Range support (Chrome needs it to seek video and audio)."""
        if not os.path.isfile(path):
            return self.send(404, {"error": "missing file"})
        size = os.path.getsize(path)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            s, _, e = rng[6:].partition("-")
            start = int(s) if s else max(0, size - int(e)); end = int(e) if (e and s) else size - 1
        length = end - start + 1
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length)); self.send_header("Cache-Control", "no-store")
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start); left = length
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (ConnectionResetError, BrokenPipeError):
                    return
                left -= len(chunk)

    def do_POST(self):
        p = urlparse(self.path).path
        if self.headers.get("Origin") and not any(h in self.headers.get("Origin", "") for h in ("127.0.0.1", "localhost")):
            return self.send(403, {"error": "local page only"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        c = arena.cfg()
        _, rev = codes(c)
        with LOCK, open(os.path.join(HERE, "picks.jsonl"), "a", encoding="utf-8") as f:
            if p == "/api/pick":
                a, b = rev.get(body.get("left")), rev.get(body.get("right"))
                if not a or not b:
                    return self.send(400, {"error": "unknown codes"})
                # stored with a = left item: "a"/"b" answers mean left/right as the owner saw them
                rec = {"id": uuid.uuid4().hex[:12], "t": time.strftime("%Y-%m-%d %H:%M:%S"), "a": a, "b": b, "left": a,
                       "answers": {m: v for m, v in (body.get("answers") or {}).items() if v in ("a", "b", "same")},
                       "bad": bool(body.get("bad")), "ms": body.get("ms"), "note": (body.get("note") or "")[:500]}
                if body.get("repeat_of"):
                    rec["repeat_of"] = body["repeat_of"]
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return self.send(200, {"ok": True, "id": rec["id"]})
            if p == "/api/undo":
                ps = arena.picks()
                if not ps:
                    return self.send(200, {"ok": False})
                f.write(json.dumps({"undo": ps[-1]["id"], "t": time.strftime("%Y-%m-%d %H:%M:%S")}) + "\n")
                return self.send(200, {"ok": True})
        return self.send(404, {"error": "not found"})


def free_port(lo=3410, hi=3499):
    for port in range(lo, hi + 1):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("no free port in 3410-3499")


if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else (arena.cfg().get("port") or free_port())
    host = "0.0.0.0" if "--lan" in sys.argv else "127.0.0.1"
    url = f"http://127.0.0.1:{port}/"
    srv = ThreadingHTTPServer((host, port), H)
    print(f"arena: {url}  ({len(arena.cfg()['items'])} items, {len(arena.picks())} picks)", flush=True)
    if "--open" in sys.argv:
        webbrowser.open(url)
    srv.serve_forever()
