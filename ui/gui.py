"""
Module giao diện người dùng - Tối ưu để không lag
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time as time_module
from typing import Dict, Optional, Callable, List
from collections import defaultdict
from core.message import Message, MessageType, EMOJI_LIST
from core.discovery import Device


class ChatGUI:
    """Giao diện chat chính"""

    def __init__(self, user_name: str, port: int):
        self.user_name = user_name
        self.port = port
        self.user_id = f"{user_name}_{port}"

        # Callbacks
        self.on_send_broadcast: Optional[Callable[[str], None]] = None
        self.on_send_private: Optional[Callable[[str, str, int], None]] = None
        self.on_send_group: Optional[Callable[[str, str], None]] = None
        self.on_create_group: Optional[Callable[[str, list], None]] = None
        self.on_scan_devices: Optional[Callable[[], None]] = None
        self.on_close: Optional[Callable[[], None]] = None

        # Chat state
        self.current_chat_id = "broadcast"
        self.current_chat_type = "broadcast"
        self.current_chat_name = "Broadcast"
        self.current_target_port = None

        # Data
        self.chat_histories: Dict[str, List[dict]] = defaultdict(list)
        self.unread_counts: Dict[str, int] = defaultdict(int)

        self._devices: Dict[str, Device] = {}
        self._groups: Dict[str, any] = {}
        self._data_lock = threading.Lock()

        # Throttling
        self._last_devices_hash = ""
        self._last_groups_hash = ""
        self._update_scheduled = False

        # Create window
        self.root = tk.Tk()
        self.root.title(f"LAN Chat - {user_name} (Port: {port})")
        self.root.geometry("950x650")
        self.root.minsize(850, 550)

        self.colors = {
            'sidebar': '#2c3e50',
            'sidebar_item': '#34495e',
            'sidebar_hover': '#4a6278',
            'chat_bg': '#ffffff',
            'unread': '#e74c3c',
            'button': '#3498db',
        }

        self._device_widgets: Dict[str, dict] = {}
        self._group_widgets: Dict[str, dict] = {}

        self._create_widgets()
        self._setup_bindings()

    def _create_widgets(self):
        """Tạo widgets"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === SIDEBAR ===
        sidebar = tk.Frame(main_frame, bg=self.colors['sidebar'], width=280)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Header
        tk.Label(
            sidebar, text=f"👤 {self.user_name}",
            bg=self.colors['sidebar'], fg='white',
            font=('Arial', 14, 'bold'), pady=15
        ).pack(fill=tk.X)

        tk.Label(
            sidebar, text=f"Port: {self.port}",
            bg=self.colors['sidebar'], fg='#95a5a6', font=('Arial', 9)
        ).pack()

        tk.Frame(sidebar, bg='#465a6e', height=1).pack(fill=tk.X, padx=10, pady=10)

        # Broadcast
        self.broadcast_frame = tk.Frame(sidebar, bg=self.colors['sidebar_item'], cursor='hand2')
        self.broadcast_frame.pack(fill=tk.X, padx=5, pady=2)

        broadcast_inner = tk.Frame(self.broadcast_frame, bg=self.colors['sidebar_item'])
        broadcast_inner.pack(fill=tk.X, padx=10, pady=8)

        self.broadcast_label = tk.Label(
            broadcast_inner, text="📢 Broadcast (Tất cả)",
            bg=self.colors['sidebar_item'], fg='white',
            font=('Arial', 11), anchor='w'
        )
        self.broadcast_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.broadcast_unread = tk.Label(
            broadcast_inner, text="",
            bg=self.colors['sidebar_item'], fg=self.colors['unread'],
            font=('Arial', 10, 'bold')
        )
        self.broadcast_unread.pack(side=tk.RIGHT)

        for w in [self.broadcast_frame, broadcast_inner, self.broadcast_label]:
            w.bind('<Button-1>', lambda e: self._select_chat("broadcast", "broadcast", "Tất cả"))

        tk.Frame(sidebar, bg='#465a6e', height=1).pack(fill=tk.X, padx=10, pady=10)

        # Devices header
        devices_header = tk.Frame(sidebar, bg=self.colors['sidebar'])
        devices_header.pack(fill=tk.X, padx=10)

        tk.Label(
            devices_header, text="🖥️ Thiết bị online",
            bg=self.colors['sidebar'], fg='white',
            font=('Arial', 11, 'bold')
        ).pack(side=tk.LEFT)

        self.devices_count = tk.Label(
            devices_header, text="(0)",
            bg=self.colors['sidebar'], fg='#7f8c8d', font=('Arial', 10)
        )
        self.devices_count.pack(side=tk.LEFT, padx=5)

        self.scan_btn = tk.Button(
            devices_header, text="🔄",
            bg=self.colors['sidebar'], fg='white',
            font=('Arial', 10), relief=tk.FLAT,
            command=self._on_scan_click
        )
        self.scan_btn.pack(side=tk.RIGHT)

        # Devices list
        self.devices_frame = tk.Frame(sidebar, bg=self.colors['sidebar'])
        self.devices_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Frame(sidebar, bg='#465a6e', height=1).pack(fill=tk.X, padx=10, pady=10)

        # Groups header
        groups_header = tk.Frame(sidebar, bg=self.colors['sidebar'])
        groups_header.pack(fill=tk.X, padx=10)

        tk.Label(
            groups_header, text="👥 Nhóm chat",
            bg=self.colors['sidebar'], fg='white',
            font=('Arial', 11, 'bold')
        ).pack(side=tk.LEFT)

        self.groups_count = tk.Label(
            groups_header, text="(0)",
            bg=self.colors['sidebar'], fg='#7f8c8d', font=('Arial', 10)
        )
        self.groups_count.pack(side=tk.LEFT, padx=5)

        # Groups list
        self.groups_frame = tk.Frame(sidebar, bg=self.colors['sidebar'])
        self.groups_frame.pack(fill=tk.X, padx=5, pady=5)

        # Buttons
        tk.Button(
            sidebar, text="➕ Tạo nhóm mới",
            bg='#27ae60', fg='white', font=('Arial', 10),
            relief=tk.FLAT, command=self._show_create_group_dialog
        ).pack(fill=tk.X, padx=10, pady=5)

        tk.Button(
            sidebar, text="🔍 Quét thiết bị",
            bg=self.colors['button'], fg='white', font=('Arial', 10),
            relief=tk.FLAT, command=self._on_scan_click
        ).pack(fill=tk.X, padx=10, pady=5)

        # === CHAT AREA ===
        chat_area = ttk.Frame(main_frame)
        chat_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(chat_area, bg='#ecf0f1', height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        self.chat_header = tk.Label(
            header, text="📢 Broadcast - Gửi đến tất cả",
            bg='#ecf0f1', font=('Arial', 13, 'bold'),
            padx=15, anchor='w'
        )
        self.chat_header.pack(fill=tk.BOTH, expand=True)

        # Chat display
        chat_container = ttk.Frame(chat_area)
        chat_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.chat_display = scrolledtext.ScrolledText(
            chat_container, wrap=tk.WORD, font=('Arial', 11),
            bg='white', state=tk.DISABLED, relief=tk.FLAT,
            padx=10, pady=10
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        self.chat_display.tag_configure("time", foreground="#888888", font=('Arial', 9))
        self.chat_display.tag_configure("sender_me", foreground="#075e54", font=('Arial', 10, 'bold'))
        self.chat_display.tag_configure("sender_other", foreground="#128c7e", font=('Arial', 10, 'bold'))
        self.chat_display.tag_configure("content", foreground="#303030")
        self.chat_display.tag_configure("system", foreground="#888888", font=('Arial', 10, 'italic'))

        # Input
        input_frame = tk.Frame(chat_area, bg='#ecf0f1', height=60)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        input_frame.pack_propagate(False)

        inner = tk.Frame(input_frame, bg='#ecf0f1')
        inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Button(
            inner, text="😀", font=('Arial', 16),
            bg='#ecf0f1', relief=tk.FLAT,
            command=self._show_emoji_picker
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.message_entry = tk.Entry(inner, font=('Arial', 12), relief=tk.FLAT, bg='white')
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Button(
            inner, text="Gửi ➤",
            bg='#128c7e', fg='white', font=('Arial', 11, 'bold'),
            relief=tk.FLAT, padx=20, command=self._send_message
        ).pack(side=tk.RIGHT)

        # Status bar
        self.status_var = tk.StringVar(value="Đang kết nối...")
        tk.Label(
            self.root, textvariable=self.status_var,
            bg='#2c3e50', fg='white', anchor='w', padx=10, pady=3
        ).pack(fill=tk.X, side=tk.BOTTOM)

    def _setup_bindings(self):
        self.message_entry.bind('<Return>', lambda e: self._send_message())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_scan_click(self):
        self.scan_btn.config(text="⏳", state=tk.DISABLED)
        self.status_var.set("🔍 Đang quét...")

        if self.on_scan_devices:
            self.on_scan_devices()

        self.root.after(2000, lambda: [
            self.scan_btn.config(text="🔄", state=tk.NORMAL),
            self.status_var.set("✅ Sẵn sàng")
        ])

    def _create_device_item(self, device_id: str, device: Device):
        """Tạo item cho device"""
        unread = self.unread_counts.get(device_id, 0)

        frame = tk.Frame(self.devices_frame, bg=self.colors['sidebar_item'], cursor='hand2')
        frame.pack(fill=tk.X, pady=2)

        inner = tk.Frame(frame, bg=self.colors['sidebar_item'])
        inner.pack(fill=tk.X, padx=10, pady=6)

        label = tk.Label(
            inner, text=f"🟢 {device.name}",
            bg=self.colors['sidebar_item'], fg='white',
            font=('Arial', 10), anchor='w'
        )
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        unread_lbl = tk.Label(
            inner, text=f"({unread})" if unread else "",
            bg=self.colors['sidebar_item'], fg=self.colors['unread'],
            font=('Arial', 9, 'bold')
        )
        unread_lbl.pack(side=tk.RIGHT)

        def on_click(e):
            self.current_target_port = device.port
            self._select_chat(device_id, "private", device.name)

        for w in [frame, inner, label, unread_lbl]:
            w.bind('<Button-1>', on_click)

        return {'frame': frame, 'unread': unread_lbl}

    def _create_group_item(self, group_id: str, group):
        """Tạo item cho group"""
        unread = self.unread_counts.get(group_id, 0)

        frame = tk.Frame(self.groups_frame, bg=self.colors['sidebar_item'], cursor='hand2')
        frame.pack(fill=tk.X, pady=2)

        inner = tk.Frame(frame, bg=self.colors['sidebar_item'])
        inner.pack(fill=tk.X, padx=10, pady=6)

        label = tk.Label(
            inner, text=f"👥 {group.name}",
            bg=self.colors['sidebar_item'], fg='white',
            font=('Arial', 10), anchor='w'
        )
        label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        unread_lbl = tk.Label(
            inner, text=f"({unread})" if unread else "",
            bg=self.colors['sidebar_item'], fg=self.colors['unread'],
            font=('Arial', 9, 'bold')
        )
        unread_lbl.pack(side=tk.RIGHT)

        def on_click(e):
            self._select_chat(group_id, "group", group.name)

        for w in [frame, inner, label, unread_lbl]:
            w.bind('<Button-1>', on_click)

        return {'frame': frame, 'unread': unread_lbl}

    def _rebuild_devices(self):
        """Rebuild devices list"""
        for w in self.devices_frame.winfo_children():
            w.destroy()
        self._device_widgets.clear()

        with self._data_lock:
            devices = dict(self._devices)

        for did, device in devices.items():
            self._device_widgets[did] = self._create_device_item(did, device)

        self.devices_count.config(text=f"({len(devices)})")

    def _rebuild_groups(self):
        """Rebuild groups list"""
        for w in self.groups_frame.winfo_children():
            w.destroy()
        self._group_widgets.clear()

        with self._data_lock:
            groups = dict(self._groups)

        for gid, group in groups.items():
            self._group_widgets[gid] = self._create_group_item(gid, group)

        self.groups_count.config(text=f"({len(groups)})")

    def _update_unread(self):
        """Update unread badges only"""
        count = self.unread_counts.get("broadcast", 0)
        self.broadcast_unread.config(text=f"({count})" if count else "")

        for did, widgets in self._device_widgets.items():
            u = self.unread_counts.get(did, 0)
            widgets['unread'].config(text=f"({u})" if u else "")

        for gid, widgets in self._group_widgets.items():
            u = self.unread_counts.get(gid, 0)
            widgets['unread'].config(text=f"({u})" if u else "")

    def _select_chat(self, chat_id: str, chat_type: str, name: str):
        self.current_chat_id = chat_id
        self.current_chat_type = chat_type
        self.current_chat_name = name

        if chat_type == "broadcast":
            self.chat_header.config(text="📢 Broadcast - Gửi đến tất cả")
        elif chat_type == "private":
            self.chat_header.config(text=f"💬 Chat với {name}")
        else:
            self.chat_header.config(text=f"👥 Nhóm: {name}")

        self.unread_counts[chat_id] = 0
        self._update_unread()
        self._display_history(chat_id)

    def _display_history(self, chat_id: str):
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)

        for msg in self.chat_histories.get(chat_id, []):
            self._insert_message(msg)

        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def _insert_message(self, msg: dict):
        t = msg.get('time', '')
        sender = msg.get('sender', '')
        content = msg.get('content', '')
        is_me = msg.get('is_me', False)
        is_system = msg.get('is_system', False)

        self.chat_display.insert(tk.END, f"[{t}] ", "time")
        if is_system:
            self.chat_display.insert(tk.END, f"{content}\n", "system")
        else:
            tag = "sender_me" if is_me else "sender_other"
            self.chat_display.insert(tk.END, f"{sender}: ", tag)
            self.chat_display.insert(tk.END, f"{content}\n", "content")

    def _add_to_history(self, chat_id: str, msg: dict):
        self.chat_histories[chat_id].append(msg)
        if len(self.chat_histories[chat_id]) > 500:
            self.chat_histories[chat_id] = self.chat_histories[chat_id][-500:]

    def _send_message(self):
        content = self.message_entry.get().strip()
        if not content:
            return

        t = time_module.strftime("%H:%M:%S")

        try:
            if self.current_chat_type == "broadcast" and self.on_send_broadcast:
                self.on_send_broadcast(content)
            elif self.current_chat_type == "private" and self.on_send_private:
                self.on_send_private(content, self.current_chat_id, self.current_target_port)
            elif self.current_chat_type == "group" and self.on_send_group:
                self.on_send_group(content, self.current_chat_id)

            msg = {'time': t, 'sender': 'Bạn', 'content': content, 'is_me': True, 'is_system': False}
            self._add_to_history(self.current_chat_id, msg)

            self.chat_display.config(state=tk.NORMAL)
            self._insert_message(msg)
            self.chat_display.see(tk.END)
            self.chat_display.config(state=tk.DISABLED)

            self.message_entry.delete(0, tk.END)
        except Exception as e:
            self.show_error(str(e))

    def _show_emoji_picker(self):
        win = tk.Toplevel(self.root)
        win.title("Emoji")
        win.geometry("340x220")
        win.transient(self.root)

        frame = ttk.Frame(win, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        row, col = 0, 0
        for emoji in EMOJI_LIST:
            tk.Button(
                frame, text=emoji, font=('Arial', 14), width=2, relief=tk.FLAT,
                command=lambda e=emoji: [
                    self.message_entry.insert(tk.END, e),
                    win.destroy()
                ]
            ).grid(row=row, column=col, padx=2, pady=2)
            col += 1
            if col >= 8:
                col = 0
                row += 1

    def _show_create_group_dialog(self):
        with self._data_lock:
            devices = dict(self._devices)

        if not devices:
            messagebox.showwarning("Thông báo", "Chưa có thiết bị!")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Tạo nhóm")
        dialog.geometry("350x400")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Tên nhóm:", font=('Arial', 11)).pack(anchor=tk.W, padx=15, pady=(15, 5))
        name_entry = tk.Entry(dialog, font=('Arial', 11), width=30)
        name_entry.pack(padx=15)
        name_entry.focus()

        tk.Label(dialog, text="Chọn thành viên:", font=('Arial', 11)).pack(anchor=tk.W, padx=15, pady=(10, 5))

        checks = {}
        for did, device in devices.items():
            var = tk.BooleanVar()
            checks[did] = var
            tk.Checkbutton(
                dialog, text=f"{device.name} ({device.port})",
                variable=var, font=('Arial', 10)
            ).pack(anchor=tk.W, padx=20)

        def create():
            name = name_entry.get().strip()
            selected = [d for d, v in checks.items() if v.get()]
            if not name or not selected:
                messagebox.showwarning("Lỗi", "Nhập tên và chọn thành viên!")
                return
            if self.on_create_group:
                self.on_create_group(name, selected)
            dialog.destroy()

        tk.Button(dialog, text="Tạo", bg='#27ae60', fg='white', command=create).pack(pady=15)

    def _on_close(self):
        if messagebox.askokcancel("Thoát", "Bạn có muốn thoát?"):
            if self.on_close:
                self.on_close()
            self.root.destroy()

    def _show_popup(self, title: str, msg: str, chat_id: str, chat_type: str, chat_name: str):
        try:
            popup = tk.Toplevel(self.root)
            popup.title("💬 Tin nhắn mới")
            popup.geometry("300x100")
            popup.attributes('-topmost', True)

            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            popup.geometry(f"+{sw-320}+{sh-160}")

            tk.Label(popup, text=title, font=('Arial', 11, 'bold')).pack(pady=5)
            tk.Label(popup, text=msg[:50], font=('Arial', 10)).pack()

            tk.Button(
                popup, text="Xem", bg='#3498db', fg='white',
                command=lambda: [self._select_chat(chat_id, chat_type, chat_name), popup.destroy()]
            ).pack(side=tk.LEFT, padx=20, pady=10)

            tk.Button(popup, text="Đóng", command=popup.destroy).pack(side=tk.RIGHT, padx=20, pady=10)

            popup.after(4000, lambda: popup.destroy() if popup.winfo_exists() else None)
        except:
            pass

    # === PUBLIC METHODS ===

    def update_devices(self, devices: Dict[str, Device]):
        """Cập nhật devices - có throttling"""
        new_hash = str(sorted([(d.device_id, d.port) for d in devices.values()]))

        if new_hash != self._last_devices_hash:
            self._last_devices_hash = new_hash
            with self._data_lock:
                self._devices = dict(devices)

            # Schedule rebuild (debounce)
            if not self._update_scheduled:
                self._update_scheduled = True
                self.root.after(500, self._do_rebuild)

    def _do_rebuild(self):
        """Thực hiện rebuild"""
        self._update_scheduled = False
        self._rebuild_devices()
        self._rebuild_groups()

    def update_groups(self, groups: dict):
        """Cập nhật groups"""
        new_hash = str(sorted([(g.group_id, g.name) for g in groups.values()]))

        if new_hash != self._last_groups_hash:
            self._last_groups_hash = new_hash
            with self._data_lock:
                self._groups = dict(groups)
            self._rebuild_groups()

    def display_received_message(self, message: Message):
        """Hiển thị tin nhắn nhận"""
        t = message.get_time_str()

        if message.msg_type == MessageType.TEXT:
            chat_id, chat_type, chat_name = "broadcast", "broadcast", "Broadcast"
        elif message.msg_type == MessageType.PRIVATE_MESSAGE:
            chat_id, chat_type, chat_name = message.sender_id, "private", message.sender_name
        elif message.msg_type == MessageType.GROUP_MESSAGE:
            chat_id = message.group_id
            chat_type = "group"
            with self._data_lock:
                g = self._groups.get(message.group_id)
            chat_name = g.name if g else f"Nhóm {message.group_id[:4]}"

            # Debug
            print(f"[DEBUG] Group message received: group={message.group_id}, from={message.sender_name}")
        else:
            return

        msg = {
            'time': t,
            'sender': message.sender_name,
            'content': message.content,
            'is_me': False,
            'is_system': False
        }
        self._add_to_history(chat_id, msg)

        if chat_id == self.current_chat_id:
            self.chat_display.config(state=tk.NORMAL)
            self._insert_message(msg)
            self.chat_display.see(tk.END)
            self.chat_display.config(state=tk.DISABLED)
        else:
            self.unread_counts[chat_id] += 1
            self._update_unread()
            self._show_popup(f"💬 {message.sender_name}", message.content, chat_id, chat_type, chat_name)

    def display_system_message(self, text: str, chat_id: str = None):
        if chat_id is None:
            chat_id = self.current_chat_id

        msg = {'time': time_module.strftime("%H:%M:%S"), 'sender': '', 'content': text, 'is_me': False, 'is_system': True}
        self._add_to_history(chat_id, msg)

        if chat_id == self.current_chat_id:
            self.chat_display.config(state=tk.NORMAL)
            self._insert_message(msg)
            self.chat_display.see(tk.END)
            self.chat_display.config(state=tk.DISABLED)

    def show_error(self, error: str):
        self.status_var.set(f"❌ {error}")

    def set_status(self, status: str):
        self.status_var.set(status)

    def run(self):
        self.root.mainloop()

    def schedule(self, func, *args):
        self.root.after(0, lambda: func(*args))