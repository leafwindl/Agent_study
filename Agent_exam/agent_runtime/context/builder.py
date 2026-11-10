from agent_runtime.session.model import Session
import json


class ContextBuilder:
    def __init__(self, max_chars: int = 6000):
        self.max_chars = max_chars
    
    def _summarize(self, dropped_messages) -> str:
        """把被丢弃的消息压成一句话。纯规则，不调模型。"""
        parts = []
        for m in dropped_messages:
            if m["role"] == "user":
                parts.append(m["content"][:30])
        if not parts:
            return ""
        return "此前用户提到：" + "；".join(parts[-5:])
    
    def build_context(self, session: Session) -> list[dict]:
        context = []
        total_chars = 0
        recent = 0

        for message in reversed(session.messages):
            message_length = len(json.dumps(message, ensure_ascii=False))
            if total_chars + message_length > self.max_chars and total_chars > 0:
                break
            context.append(message)
            total_chars += message_length
            recent += 1
        if recent < len(session.messages):
            abstract = self._summarize(session.messages[:-recent])
            if abstract:
                context.append({"role": "system", "content": abstract})
        context.reverse()
        return context