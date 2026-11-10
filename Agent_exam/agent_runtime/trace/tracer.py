from typing import Protocol

class Tracer(Protocol):
    def log(self, kind: str, **fields): ...


class PrintTracer:
    def log(self, kind: str, **fields):
        print(f"[{kind}] " + " ".join(f"{k}={v}" for k, v in fields.items()))


class NoopTracer:
    def log(self, kind: str, **fields):
        pass