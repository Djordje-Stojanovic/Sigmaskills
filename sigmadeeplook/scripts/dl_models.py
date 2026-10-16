"""Model files the look can use when they are already on this machine. Never downloads (no network code lives here)."""
import os
from pathlib import Path

import dl_core as core

HF_DIRS = {"ast": "models--MIT--ast-finetuned-audioset-10-10-0.4593", "pyannote": "models--pyannote--speaker-diarization-community-1"}
WHISPER_ORDER_FAST = ("large-v3", "medium", "small", "base", "tiny")


def hf_hub():
    return Path(os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")) / "hub"


def models_dir():
    return Path(os.environ.get("SIGMADEEPLOOK_MODELS") or core.cache_root() / "models")


def hf_snapshot(name):
    """-> the snapshot folder of a cached Hugging Face model, or None."""
    d = hf_hub() / HF_DIRS[name] / "snapshots"
    if d.is_dir():
        snaps = sorted(p for p in d.iterdir() if p.is_dir())
        if snaps:
            return snaps[-1]
    return None


def yunet_path():
    for c in (models_dir() / "face_detection_yunet_2023mar.onnx", Path(os.path.expanduser("~/.cache/opencv_zoo/face_detection_yunet_2023mar.onnx"))):
        if c.exists():
            return c
    return None


def have_model(name):
    if name in core.HIDE:
        return False
    if name == "yunet":
        return yunet_path() is not None
    if name in HF_DIRS:
        return hf_snapshot(name) is not None
    return False
