from agent_runtime.session.model import Session
from agent_runtime.session.base import SessionStore

class InMemorySessionStore(SessionStore):
    def __init__(self):
        self.sessions: dict[str, dict] = {}

    def save(self, session: Session) -> None:
        self.sessions[session.id] = {
            "id": session.id,
            "messages": list(session.messages),
            "todos": list(session.todos),
            "created_at": session.created_at,
            "updated_at": session.updated_at
        }

    def load(self, session_id: str) -> Session | None:
        session_data = self.sessions.get(session_id)
        if session_data is None:
            return None
        return Session(
            id=session_data["id"],
            messages=list(session_data["messages"]),
            todos=list(session_data["todos"]),
            created_at=session_data["created_at"],
            updated_at=session_data["updated_at"]
        )