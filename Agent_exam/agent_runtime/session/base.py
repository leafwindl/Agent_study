from typing import Protocol
from agent_runtime.session.model import Session

class SessionStore(Protocol):
    def save(self, session: Session) -> None:
        ...

    def load(self, session_id: str) -> Session | None:
        ...