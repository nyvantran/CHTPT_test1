"""
Module quản lý nhóm chat - Sửa lỗi đồng bộ thành viên
"""
import uuid
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field
from .message import Message, MessageType
from utils.logger import Logger


@dataclass
class Group:
    """Thông tin nhóm"""
    group_id: str
    name: str
    creator_id: str
    member_ids: Set[str] = field(default_factory=set)
    member_ports: Dict[str, int] = field(default_factory=dict)  # member_id -> port
    member_names: Dict[str, str] = field(default_factory=dict)  # member_id -> name

    def add_member(self, member_id: str, port: int, name: str = ""):
        """Thêm thành viên"""
        self.member_ids.add(member_id)
        self.member_ports[member_id] = port
        if name:
            self.member_names[member_id] = name

    def remove_member(self, member_id: str):
        """Xóa thành viên"""
        self.member_ids.discard(member_id)
        self.member_ports.pop(member_id, None)
        self.member_names.pop(member_id, None)

    def is_member(self, member_id: str) -> bool:
        """Kiểm tra có phải thành viên không"""
        return member_id in self.member_ids

    def get_all_ports(self) -> List[int]:
        """Lấy tất cả port của thành viên"""
        return list(self.member_ports.values())

    def get_other_ports(self, exclude_id: str) -> List[int]:
        """Lấy port của các thành viên khác (trừ mình)"""
        return [port for mid, port in self.member_ports.items() if mid != exclude_id]

    def to_dict(self) -> dict:
        """Chuyển thành dict để gửi qua mạng"""
        return {
            'group_id': self.group_id,
            'name': self.name,
            'creator_id': self.creator_id,
            'member_ids': list(self.member_ids),
            'member_ports': self.member_ports,
            'member_names': self.member_names
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Group':
        """Tạo Group từ dict"""
        group = cls(
            group_id=data['group_id'],
            name=data['name'],
            creator_id=data['creator_id']
        )
        group.member_ids = set(data.get('member_ids', []))
        group.member_ports = data.get('member_ports', {})
        group.member_names = data.get('member_names', {})
        return group


class GroupManager:
    """Quản lý các nhóm chat"""

    def __init__(self, network_manager, logger: Logger):
        self.network = network_manager
        self.logger = logger
        self.groups: Dict[str, Group] = {}

    def create_group(self, name: str, member_ids: List[str], member_info: Dict[str, dict]) -> Group:
        """
        Tạo nhóm mới
        member_info: {member_id: {'port': int, 'name': str}}
        """
        group_id = str(uuid.uuid4())[:8]

        group = Group(
            group_id=group_id,
            name=name,
            creator_id=self.network.user_id
        )

        # Thêm người tạo vào nhóm
        group.add_member(
            self.network.user_id,
            self.network.port,
            self.network.user_name
        )

        # Thêm các thành viên được chọn
        for member_id in member_ids:
            if member_id in member_info:
                info = member_info[member_id]
                group.add_member(member_id, info['port'], info.get('name', ''))

        self.groups[group_id] = group

        # Gửi thông báo tạo nhóm đến TẤT CẢ thành viên
        self._broadcast_group_info(group)

        self.logger.info(f"Created group: {name} with {len(group.member_ids)} members")
        return group

    def _broadcast_group_info(self, group: Group):
        """Gửi thông tin nhóm đến tất cả thành viên"""
        import json

        # Đóng gói toàn bộ thông tin nhóm
        group_data = json.dumps(group.to_dict())

        msg = Message(
            msg_type=MessageType.GROUP_CREATE,
            sender_id=self.network.user_id,
            sender_name=self.network.user_name,
            sender_port=self.network.port,
            content=group_data,  # Gửi toàn bộ thông tin nhóm
            group_id=group.group_id,
            group_members=list(group.member_ids)
        )

        # Gửi đến tất cả thành viên (trừ mình)
        for member_id, port in group.member_ports.items():
            if member_id != self.network.user_id:
                self.network._send_to_port(msg, port)
                self.logger.debug(f"Sent group info to {member_id} at port {port}")

    def handle_group_create(self, message: Message) -> Optional[Group]:
        """Xử lý khi nhận thông báo tạo nhóm"""
        import json

        try:
            # Parse thông tin nhóm từ content
            group_data = json.loads(message.content)

            group_id = group_data['group_id']

            # Nếu đã có nhóm này, cập nhật thông tin
            if group_id in self.groups:
                existing = self.groups[group_id]
                # Merge thông tin
                existing.member_ids.update(group_data.get('member_ids', []))
                existing.member_ports.update(group_data.get('member_ports', {}))
                existing.member_names.update(group_data.get('member_names', {}))
                return existing

            # Tạo nhóm mới từ dữ liệu nhận được
            group = Group.from_dict(group_data)

            # Đảm bảo bản thân được thêm vào
            if self.network.user_id not in group.member_ids:
                group.add_member(
                    self.network.user_id,
                    self.network.port,
                    self.network.user_name
                )

            self.groups[group_id] = group

            self.logger.info(f"Joined group: {group.name} ({len(group.member_ids)} members)")
            self.logger.debug(f"Group members: {group.member_ports}")

            return group

        except Exception as e:
            self.logger.error(f"Failed to parse group info: {e}")
            return None

    def send_group_message(self, group_id: str, content: str):
        """Gửi tin nhắn đến nhóm"""
        if group_id not in self.groups:
            self.logger.error(f"Group {group_id} not found")
            return

        group = self.groups[group_id]

        msg = Message(
            msg_type=MessageType.GROUP_MESSAGE,
            sender_id=self.network.user_id,
            sender_name=self.network.user_name,
            sender_port=self.network.port,
            content=content,
            group_id=group_id
        )

        # Gửi đến tất cả thành viên KHÁC trong nhóm
        sent_count = 0
        for member_id, port in group.member_ports.items():
            if member_id != self.network.user_id:
                self.network._send_to_port(msg, port)
                sent_count += 1
                self.logger.debug(f"Sent group msg to {member_id} at port {port}")

        self.logger.debug(f"Group message sent to {sent_count} members")

    def is_group_message_for_me(self, message: Message) -> bool:
        """Kiểm tra tin nhắn nhóm có dành cho mình không"""
        group_id = message.group_id

        if group_id not in self.groups:
            # Có thể nhóm được tạo nhưng mình chưa nhận được thông tin
            self.logger.debug(f"Group {group_id} not found locally")
            return False

        group = self.groups[group_id]
        is_member = group.is_member(self.network.user_id)

        self.logger.debug(f"Is member of {group_id}: {is_member}")
        return is_member

    def get_group(self, group_id: str) -> Optional[Group]:
        """Lấy thông tin nhóm"""
        return self.groups.get(group_id)

    def get_all_groups(self) -> Dict[str, Group]:
        """Lấy tất cả nhóm"""
        return self.groups

    def update_member_port(self, member_id: str, port: int, name: str = ""):
        """Cập nhật port của thành viên trong tất cả các nhóm"""
        for group in self.groups.values():
            if member_id in group.member_ids:
                group.member_ports[member_id] = port
                if name:
                    group.member_names[member_id] = name