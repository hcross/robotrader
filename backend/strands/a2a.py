import json
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

@dataclass
class Message:
    sender: str
    recipient: str
    msg_type: str  # e.g., "GOAL", "INSIGHT", "REQUEST", "RESPONSE"
    content: Any
    timestamp: float = 0.0
    id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(json_str: str) -> 'Message':
        data = json.loads(json_str)
        return Message(**data)
