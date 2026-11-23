"""model_env.py - the model values of box/model.env for the Python box scripts; a set environment variable wins."""
import os

KEYS = ("MODEL_ID", "MODEL_REVISION", "MODEL_DIR", "SERVED_NAME", "OVERLAY_ID")
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.env")


def model_env(path=ENV_FILE):
    values = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"')
    values.update({k: os.environ[k] for k in KEYS if os.environ.get(k)})
    unset = [k for k in KEYS[:4] if not values.get(k) or "<" in values[k]]
    if unset:
        raise SystemExit(f"set {', '.join(unset)} in box/model.env")
    return values
