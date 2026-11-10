from dataclasses import dataclass

@dataclass
class Session:
    id: str
    messages: list[dict]
    todos: list[str]
    created_at: float
    updated_at: float
