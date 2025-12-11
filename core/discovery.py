"""
Module dò tìm các máy trong mạng - Tối ưu để không gây lag
"""
import threading
import time
from typing import Dict, Callable, Optional
from dataclasses import dataclass
from .message import Message, MessageType
from utils.logger import Logger


@dataclass
class Device:
    """Thông tin thiết bị"""
    device_id: str
    name: str
    port: int
    last_seen: float

    def is_online(self, timeout: float = 60.0) -> bool:
        return (time.time() - self.last_seen) < timeout


class DeviceDiscovery:
    """Quản lý việc dò tìm thiết bị"""

    DISCOVERY_INTERVAL = 15.0  # 15 giây
    DEVICE_TIMEOUT = 60.0      # 60 giây mới coi là offline

    def __init__(self, network_manager, logger: Logger):
        self.network = network_manager
        self.logger = logger

        self.devices: Dict[str, Device] = {}
        self._devices_lock = threading.Lock()
        self.running = False

        # Flags để throttle updates
        self._pending_update = False
        self._last_update_time = 0
        self._update_cooldown = 2.0  # Chỉ update GUI mỗi 2 giây

        self.on_device_found: Optional[Callable[[Device], None]] = None
        self.on_device_lost: Optional[Callable[[Device], None]] = None
        self.on_devices_updated: Optional[Callable[[Dict[str, Device]], None]] = None

    def start(self):
        """Bắt đầu dò tìm"""
        self.running = True

        # Discovery thread
        discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        discovery_thread.start()

        # Cleanup thread
        cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        cleanup_thread.start()

        # Update throttle thread
        update_thread = threading.Thread(target=self._update_loop, daemon=True)
        update_thread.start()

        self.logger.info("Device discovery started")

    def stop(self):
        """Dừng dò tìm"""
        self.running = False

    def send_discovery_now(self):
        """Gửi discovery ngay lập tức"""
        try:
            msg = Message(
                msg_type=MessageType.DISCOVERY,
                sender_id=self.network.user_id,
                sender_name=self.network.user_name,
                sender_port=self.network.port,
                content="discover"
            )
            self.network.send_message(msg)
        except Exception as e:
            self.logger.error(f"Discovery error: {e}")

    def handle_discovery_message(self, message: Message):
        """Xử lý tin nhắn discovery"""
        if message.msg_type == MessageType.DISCOVERY:
            # Delay nhỏ để tránh flood
            threading.Timer(0.1, self._send_discovery_response, args=[message.sender_port]).start()
            self._add_device(message)

        elif message.msg_type == MessageType.DISCOVERY_RESPONSE:
            self._add_device(message)

    def _send_discovery_response(self, target_port: int):
        """Gửi response sau delay"""
        try:
            response = Message(
                msg_type=MessageType.DISCOVERY_RESPONSE,
                sender_id=self.network.user_id,
                sender_name=self.network.user_name,
                sender_port=self.network.port,
                content="online"
            )
            self.network._send_to_port(response, target_port)
        except:
            pass

    def _add_device(self, message: Message):
        """Thêm hoặc cập nhật thiết bị"""
        device_id = message.sender_id

        with self._devices_lock:
            is_new = device_id not in self.devices

            self.devices[device_id] = Device(
                device_id=device_id,
                name=message.sender_name,
                port=message.sender_port,
                last_seen=time.time()
            )

        if is_new:
            self.logger.info(f"Device found: {message.sender_name}")
            if self.on_device_found:
                try:
                    self.on_device_found(self.devices[device_id])
                except:
                    pass

        # Đánh dấu cần update (sẽ được xử lý bởi update_loop)
        self._pending_update = True

    def _schedule_update(self):
        """Lên lịch update GUI"""
        current_time = time.time()
        if current_time - self._last_update_time >= self._update_cooldown:
            self._last_update_time = current_time
            self._pending_update = False

            with self._devices_lock:
                devices_copy = dict(self.devices)

            if self.on_devices_updated:
                try:
                    self.on_devices_updated(devices_copy)
                except:
                    pass

    def _update_loop(self):
        """Thread xử lý update GUI với throttling"""
        while self.running:
            if self._pending_update:
                self._schedule_update()
            time.sleep(0.5)

    def _discovery_loop(self):
        """Gửi discovery định kỳ"""
        # Đợi 1 giây trước khi bắt đầu
        time.sleep(1.0)

        while self.running:
            try:
                msg = Message(
                    msg_type=MessageType.DISCOVERY,
                    sender_id=self.network.user_id,
                    sender_name=self.network.user_name,
                    sender_port=self.network.port,
                    content="discover"
                )
                self.network.send_message(msg)
            except Exception as e:
                self.logger.error(f"Discovery error: {e}")

            time.sleep(self.DISCOVERY_INTERVAL)

    def _cleanup_loop(self):
        """Xóa thiết bị offline"""
        while self.running:
            time.sleep(15.0)  # Check mỗi 15 giây

            try:
                offline_devices = []

                with self._devices_lock:
                    for device_id, device in list(self.devices.items()):
                        if not device.is_online(self.DEVICE_TIMEOUT):
                            offline_devices.append((device_id, device))

                    for device_id, _ in offline_devices:
                        del self.devices[device_id]

                for _, device in offline_devices:
                    self.logger.info(f"Device lost: {device.name}")
                    if self.on_device_lost:
                        try:
                            self.on_device_lost(device)
                        except:
                            pass

                if offline_devices:
                    self._pending_update = True

            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")

    def get_online_devices(self) -> Dict[str, Device]:
        """Lấy danh sách thiết bị online"""
        with self._devices_lock:
            return {k: v for k, v in self.devices.items() if v.is_online()}