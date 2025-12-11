"""
Main application - Sửa lỗi tạo nhóm
"""
import sys
import argparse
from core import NetworkManager, DeviceDiscovery, GroupManager
from core.message import Message, MessageType
from ui import ChatGUI
from utils import Logger


class ChatApplication:
    """Ứng dụng chat chính"""

    def __init__(self, user_name: str, port: int):
        self.user_name = user_name
        self.port = port

        self.logger = Logger(f"{user_name}_{port}")
        self.logger.on_error = self._on_error

        self.network = NetworkManager(port, user_name, self.logger)
        self.discovery = DeviceDiscovery(self.network, self.logger)
        self.groups = GroupManager(self.network, self.logger)

        self.gui = ChatGUI(user_name, port)

        self._setup_callbacks()

    def _setup_callbacks(self):
        """Thiết lập callbacks"""
        # GUI -> Core
        self.gui.on_send_broadcast = self._send_broadcast
        self.gui.on_send_private = self._send_private
        self.gui.on_send_group = self._send_group
        self.gui.on_create_group = self._create_group
        self.gui.on_scan_devices = self._scan_devices
        self.gui.on_close = self._on_close

        # Core -> GUI
        self.network.on_message_received = self._on_message_received
        self.network.on_error = self._on_error

        self.discovery.on_devices_updated = lambda d: self.gui.schedule(self.gui.update_devices, d)
        self.discovery.on_device_found = lambda d: self._on_device_found(d)
        self.discovery.on_device_lost = lambda d: self.gui.schedule(
            self.gui.display_system_message, f"🔴 {d.name} đã offline", "broadcast"
        )

    def _on_device_found(self, device):
        """Xử lý khi tìm thấy thiết bị mới"""
        self.gui.schedule(
            self.gui.display_system_message,
            f"🟢 {device.name} đã online",
            "broadcast"
        )

        # Cập nhật port của thiết bị trong các nhóm
        self.groups.update_member_port(device.device_id, device.port, device.name)

    def start(self):
        """Khởi động ứng dụng"""
        self.logger.info(f"Starting {self.user_name} on port {self.port}")

        if not self.network.start():
            return False

        self.discovery.start()
        self.gui.set_status(f"✅ Sẵn sàng - Port {self.port}")
        self.gui.run()

        return True

    def _scan_devices(self):
        """Quét thiết bị"""
        self.discovery.send_discovery_now()

    def _send_broadcast(self, content: str):
        """Gửi broadcast"""
        self.network.broadcast_message(content, MessageType.TEXT)

    def _send_private(self, content: str, target_id: str, target_port: int):
        """Gửi tin nhắn riêng"""
        self.network.send_private_message(content, target_id, target_port)

    def _send_group(self, content: str, group_id: str):
        """Gửi tin nhắn nhóm"""
        self.groups.send_group_message(group_id, content)

    def _create_group(self, name: str, member_ids: list):
        """Tạo nhóm mới"""
        # Lấy thông tin đầy đủ của các thành viên
        member_info = {}
        for device_id, device in self.discovery.devices.items():
            if device_id in member_ids:
                member_info[device_id] = {
                    'port': device.port,
                    'name': device.name
                }

        if not member_info:
            self.gui.schedule(self.gui.show_error, "Không tìm thấy thành viên!")
            return

        group = self.groups.create_group(name, member_ids, member_info)

        self.gui.schedule(self.gui.update_groups, self.groups.get_all_groups())
        self.gui.schedule(
            self.gui.display_system_message,
            f"✅ Đã tạo nhóm '{name}' với {len(group.member_ids)} thành viên",
            "broadcast"
        )

    def _on_message_received(self, message: Message):
        """Xử lý tin nhắn nhận được"""
        msg_type = message.msg_type

        if msg_type in [MessageType.DISCOVERY, MessageType.DISCOVERY_RESPONSE]:
            self.discovery.handle_discovery_message(message)

        elif msg_type == MessageType.TEXT:
            self.gui.schedule(self.gui.display_received_message, message)

        elif msg_type == MessageType.PRIVATE_MESSAGE:
            if message.target_id == self.network.user_id:
                self.gui.schedule(self.gui.display_received_message, message)

        elif msg_type == MessageType.GROUP_MESSAGE:
            # Kiểm tra xem mình có trong nhóm không
            if self.groups.is_group_message_for_me(message):
                self.gui.schedule(self.gui.display_received_message, message)
            else:
                self.logger.debug(f"Ignored group message for {message.group_id}")

        elif msg_type == MessageType.GROUP_CREATE:
            # Nhận thông báo được thêm vào nhóm
            group = self.groups.handle_group_create(message)
            if group:
                self.gui.schedule(self.gui.update_groups, self.groups.get_all_groups())
                self.gui.schedule(
                    self.gui.display_system_message,
                    f"👥 Bạn đã được thêm vào nhóm: {group.name}",
                    "broadcast"
                )

    def _on_error(self, error: str):
        """Xử lý lỗi"""
        self.gui.schedule(self.gui.show_error, error)

    def _on_close(self):
        """Đóng ứng dụng"""
        self.discovery.stop()
        self.network.stop()


def main():
    parser = argparse.ArgumentParser(description='LAN Chat')
    parser.add_argument('-n', '--name', type=str, required=True)
    parser.add_argument('-p', '--port', type=int, default=5000)

    args = parser.parse_args()

    if args.port < 1024 or args.port > 65535:
        print("Port phải từ 1024-65535")
        sys.exit(1)

    app = ChatApplication(args.name, args.port)

    try:
        app.start()
    except KeyboardInterrupt:
        print("\nTạm biệt!")
    except Exception as e:
        print(f"Lỗi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()