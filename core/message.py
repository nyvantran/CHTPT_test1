"""
Module định dạng tin nhắn
"""
import json
import time
import uuid
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, List


class MessageType(Enum):
    """Loại tin nhắn"""
    TEXT = "text"
    DISCOVERY = "discovery"
    DISCOVERY_RESPONSE = "discovery_response"
    GROUP_CREATE = "group_create"
    GROUP_INVITE = "group_invite"
    GROUP_MESSAGE = "group_message"
    PRIVATE_MESSAGE = "private_message"
    HEARTBEAT = "heartbeat"
    EMOJI = "emoji"


@dataclass
class Message:
    """Class đại diện cho tin nhắn"""
    msg_type: MessageType
    sender_id: str
    sender_name: str
    sender_port: int
    content: str
    timestamp: float = None
    msg_id: str = None
    target_id: Optional[str] = None
    group_id: Optional[str] = None
    group_members: Optional[List[str]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.msg_id is None:
            self.msg_id = str(uuid.uuid4())[:8]

    def to_json(self) -> str:
        """Chuyển đổi thành JSON string"""
        data = asdict(self)
        data['msg_type'] = self.msg_type.value
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Tạo Message từ JSON string"""
        try:
            data = json.loads(json_str)
            data['msg_type'] = MessageType(data['msg_type'])
            return cls(**data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Invalid message format: {e}")

    def get_time_str(self) -> str:
        """Lấy thời gian dạng string"""
        return time.strftime("%H:%M:%S", time.localtime(self.timestamp))

    def get_chat_id(self) -> str:
        """Lấy ID của cuộc trò chuyện"""
        if self.msg_type == MessageType.GROUP_MESSAGE:
            return f"group_{self.group_id}"
        elif self.msg_type == MessageType.PRIVATE_MESSAGE:
            return f"private_{self.sender_id}"
        else:
            return "broadcast"


# Danh sách emoji phổ biến
EMOJI_LIST = [
    "😀", "😃", "😄", "😁", "😅", "😂", "🤣", "😊",
    "😇", "🙂", "😉", "😍", "🥰", "😘", "😋", "😎",
    "🤔", "🤨", "😐", "😑", "😶", "🙄", "😏", "😣",
    "😥", "😮", "🤐", "😯", "😪", "😫", "🥱", "😴",
    "😌", "😛", "😜", "😝", "🤤", "😒", "😓", "😔",
    "👍", "👎", "👏", "🙌", "🤝", "❤️", "💔", "💯",
    "🔥", "⭐", "🎉", "🎊", "💪", "🙏", "✅", "❌"
]