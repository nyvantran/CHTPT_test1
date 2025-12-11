"""
Module xử lý mạng - Thêm retry cho tin nhắn quan trọng
"""
import socket
import threading
import queue
import time
from typing import Callable, Optional, Set
from .message import Message, MessageType
from utils.logger import Logger


class NetworkManager:
    """Quản lý kết nối mạng"""

    BUFFER_SIZE = 65535

    def __init__(self, port: int, user_name: str, logger: Logger):
        self.port = port
        self.user_name = user_name
        self.user_id = f"{user_name}_{port}"
        self.logger = logger

        self.incoming_queue = queue.Queue(maxsize=100)
        self.outgoing_queue = queue.Queue(maxsize=100)

        self.processed_messages: Set[str] = set()
        self._processed_lock = threading.Lock()

        self.recv_socket: Optional[socket.socket] = None
        self.send_socket: Optional[socket.socket] = None

        self.running = False

        self.on_message_received: Optional[Callable[[Message], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    def start(self) -> bool:
        """Khởi động"""
        try:
            self.recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except:
                pass
            self.recv_socket.bind(("", self.port))
            self.recv_socket.settimeout(0.5)

            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            self.running = True

            threading.Thread(target=self._receive_loop, daemon=True).start()
            threading.Thread(target=self._send_loop, daemon=True).start()
            threading.Thread(target=self._process_loop, daemon=True).start()
            threading.Thread(target=self._cleanup_loop, daemon=True).start()

            self.logger.info(f"Network started on port {self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Network start failed: {e}")
            return False

    def stop(self):
        """Dừng"""
        self.running = False
        try:
            if self.recv_socket:
                self.recv_socket.close()
            if self.send_socket:
                self.send_socket.close()
        except:
            pass

    def send_message(self, message: Message):
        """Gửi tin nhắn"""
        try:
            self.outgoing_queue.put_nowait(message)
        except queue.Full:
            pass

    def broadcast_message(self, content: str, msg_type: MessageType = MessageType.TEXT):
        """Gửi broadcast"""
        msg = Message(
            msg_type=msg_type,
            sender_id=self.user_id,
            sender_name=self.user_name,
            sender_port=self.port,
            content=content
        )
        self.send_message(msg)

    def send_private_message(self, content: str, target_id: str, target_port: int):
        """Gửi riêng"""
        msg = Message(
            msg_type=MessageType.PRIVATE_MESSAGE,
            sender_id=self.user_id,
            sender_name=self.user_name,
            sender_port=self.port,
            content=content,
            target_id=target_id
        )
        self._send_to_port(msg, target_port)

    def send_group_message(self, content: str, group_id: str, member_ports: list):
        """Gửi nhóm"""
        msg = Message(
            msg_type=MessageType.GROUP_MESSAGE,
            sender_id=self.user_id,
            sender_name=self.user_name,
            sender_port=self.port,
            content=content,
            group_id=group_id
        )

        for port in member_ports:
            if port != self.port:
                # Gửi 2 lần để đảm bảo (UDP không tin cậy)
                self._send_to_port(msg, port)
                time.sleep(0.05)
                self._send_to_port(msg, port)

    def _send_to_port(self, message: Message, target_port: int):
        """Gửi đến port"""
        try:
            data = message.to_json().encode('utf-8')
            self.send_socket.sendto(data, ("127.0.0.1", target_port))
        except Exception as e:
            self.logger.error(f"Send to port {target_port} failed: {e}")

    def _is_duplicate(self, msg_id: str) -> bool:
        """Kiểm tra trùng"""
        with self._processed_lock:
            if msg_id in self.processed_messages:
                return True
            self.processed_messages.add(msg_id)
            return False

    def _receive_loop(self):
        """Nhận tin"""
        while self.running:
            try:
                data, addr = self.recv_socket.recvfrom(self.BUFFER_SIZE)
                message = Message.from_json(data.decode('utf-8'))

                if message.sender_id == self.user_id:
                    continue

                if self._is_duplicate(message.msg_id):
                    continue

                self.incoming_queue.put_nowait(message)
            except socket.timeout:
                continue
            except queue.Full:
                pass
            except:
                pass

    def _send_loop(self):
        """Gửi tin"""
        while self.running:
            try:
                message = self.outgoing_queue.get(timeout=0.5)
                data = message.to_json().encode('utf-8')

                for port in range(5000, 5010):
                    if port != self.port:
                        try:
                            self.send_socket.sendto(data, ("127.0.0.1", port))
                        except:
                            pass

                time.sleep(0.01)
            except queue.Empty:
                continue
            except:
                pass

    def _process_loop(self):
        """Xử lý tin"""
        while self.running:
            try:
                message = self.incoming_queue.get(timeout=0.5)
                if self.on_message_received:
                    self.on_message_received(message)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Process error: {e}")

    def _cleanup_loop(self):
        """Dọn cache"""
        while self.running:
            time.sleep(60)
            with self._processed_lock:
                if len(self.processed_messages) > 500:
                    self.processed_messages.clear()