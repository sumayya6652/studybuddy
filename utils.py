import os
from contextlib import contextmanager
from time import perf_counter

def ensure_dirs():
    os.makedirs("data/uploads", exist_ok=True)
    os.makedirs("data/index", exist_ok=True)

@contextmanager
def timer(name: str):
    t0 = perf_counter()
    yield
    dt = perf_counter() - t0
    print(f"[{name}] {dt:.2f}s")
