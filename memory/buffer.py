from .models import Message


class ConversationBuffer:
    def __init__(self, max_turns: int = 8):
        self._messages: list[Message] = []
        self.max_turns = max_turns      # each turn = 1 user + 1 assistant msg
        self.current_turn: int = 0

    # ── Write ────────────────────────────────────────────────────

    def add_user_message(self, content: str) -> Message:
        self.current_turn += 1
        msg = Message(role="user", content=content, turn_id=self.current_turn)
        self._messages.append(msg)
        self._trim()
        return msg

    def add_assistant_message(self, content: str) -> Message:
        msg = Message(role="assistant", content=content, turn_id=self.current_turn)
        self._messages.append(msg)
        self._trim()
        return msg

    # ── Read ─────────────────────────────────────────────────────

    def get_history(self) -> list[dict]:
        """Return messages in the format the LLM API expects."""
        return [{"role": m.role, "content": m.content} for m in self._messages]

    def get_recent_messages(self, max_messages: int = 8) -> list[dict]:
        """Return the most recent messages for prompt context."""
        return [{"role": m.role, "content": m.content} for m in self._messages[-max_messages:]]

    def get_last_user_message(self) -> str | None:
        for msg in reversed(self._messages):
            if msg.role == "user":
                return msg.content
        return None

    def get_turn_messages(self, turn_id: int) -> list[Message]:
        """Retrieve all messages from a specific turn."""
        return [m for m in self._messages if m.turn_id == turn_id]

    def is_empty(self) -> bool:
        return len(self._messages) == 0

    # ── Internal ─────────────────────────────────────────────────

    def _trim(self):
        """Keep only the last max_turns pairs (user + assistant = 1 turn)."""
        max_messages = self.max_turns * 2
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]

    # ── Serialization (used by session.py) ───────────────────────

    def to_dict(self) -> dict:
        return {
            "messages": [vars(m) for m in self._messages],
            "max_turns": self.max_turns,
            "current_turn": self.current_turn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationBuffer":
        buf = cls(max_turns=data["max_turns"])
        buf.current_turn = data["current_turn"]
        buf._messages = [Message(**m) for m in data["messages"]]
        return buf