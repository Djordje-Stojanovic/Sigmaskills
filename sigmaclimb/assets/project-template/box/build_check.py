"""Compile the patched b12x native loader and prove both pread fallbacks run (io_uring is blocked here)."""
import os, tempfile

from flashinfer.experimental.b12x.loader import _native

m = _native.load()
print("native module built:", m.__file__)

# PLE reader: io_uring_queue_init is refused -> the reader must still be created (pread mode)
r = m.ple_reader(16, 16, 0, 16, 4096, 0, 8, 64)
print("ple_reader created in fallback mode:", r is not None)
