from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


@dataclass
class Message:
    role: str        # "user" or "assistant"
    content: str
    turn_id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ToolCall:
    tool_name: str
    params: dict
    result: Any
    turn: Optional[int] = None        # which conversation turn triggered this
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class UserContext:
    home_location: Optional[str] = None
    work_location: Optional[str] = None
    preferred_modes: list = field(default_factory=list)
    avoid_modes: list = field(default_factory=list)
    budget_preference: Optional[str] = None   # "low", "medium", "high"
    accessibility_needs: bool = False
    recent_locations: list = field(default_factory=list)
    language: str = "ar"