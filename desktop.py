import json
import threading
import time
import tkinter as tk
from tkinter import scrolledtext
from queue import Queue
import os
import sys
import subprocess
import requests
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import websocket
import pyperclip
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw


class ClippyDesktop:
    def __init__(self):
        self.server_url = "ws://localhost:8948/ws"
        self.server_http_url = "http://localhost:8948"
        self.ws = None
        self.ws_thread = None
        self.reconnect_delay = 5

        # 消息队列，用于线程间通信
        self.message_queue = Queue()

        # 托盘图标
        self.tray_icon = None

        # GUI窗口
        self.window = None
        self.popup_window = None
        self.text_widget = None

        # 当前文本内容
        self.current_text = ""

        # 服务器连接状态
        self.server_connected = False
        self.auto_reconnect = True  # 是否自动重连

        # 开机启动路径
        self.startup_folder = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )
        self.startup_shortcut = os.path.join(self.startup_folder, 'Clippy.lnk')

        # 获取当前脚本目录
        if getattr(sys, 'frozen', False):
            # 打包后的exe
            self.app_dir = os.path.dirname(sys.executable)
        else:
            # Python脚本
            self.app_dir = os.path.dirname(os.path.abspath(__file__))

        self.vbs_path = os.path.join(self.app_dir, 'start-clippy-silent.vbs')

    def create_main_window(self):
        """创建主窗口（隐藏，用于托盘）"""
        self.window = ttk.Window(themename="cosmo")
        self.window.title("Clippy")
        self.window.geometry("1x1")
        self.window.withdraw()  # 隐藏主窗口
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_popup_window(self):
        """创建弹窗"""
        if self.popup_window:
            return

        self.popup_window = tk.Toplevel(self.window)
        self.popup_window.title("Clippy")
        self.popup_window.geometry("400x250")
        self.popup_window.withdraw()  # 初始隐藏

        # 设置窗口位置在右下角
        self.popup_window.update_idletasks()
        screen_width = self.popup_window.winfo_screenwidth()
        screen_height = self.popup_window.winfo_screenheight()
        window_width = 400
        window_height = 250
        x = screen_width - window_width - 20
        y = screen_height - window_height - 120
        self.popup_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # 关闭按钮改为隐藏
        self.popup_window.protocol("WM_DELETE_WINDOW", self.hide_popup)

        # 创建主框架
        main_frame = ttk.Frame(self.popup_window, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

        # 复制按钮（放在最上面）
        copy_btn = ttk.Button(
            main_frame,
            text="复制",
            bootstyle=PRIMARY,
            command=self.copy_text
        )
        copy_btn.pack(fill=X, pady=(0, 10))

        # 文本显示区域
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=BOTH, expand=YES)

        self.text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei UI", 10),
            state='disabled'
        )
        self.text_widget.pack(fill=BOTH, expand=YES)

    def create_tray_icon(self):
        """创建托盘图标（在后台线程运行）"""
        # 创建绿色图标（默认）
        image = self.create_icon_image('#4CAF50', '#2E7D32')

        menu = Menu(
            MenuItem('显示窗口', self.show_popup_from_tray),
            Menu.SEPARATOR,
            MenuItem(
                '开机启动',
                self.toggle_startup_from_tray,
                checked=lambda item: self.is_startup_enabled()
            ),
            MenuItem(
                '启动服务器',
                self.start_server_from_tray,
                visible=lambda item: not self.check_server_status()
            ),
            MenuItem(
                '重启服务器',
                self.restart_server_from_tray,
                visible=lambda item: self.check_server_status()
            ),
            MenuItem(
                '关闭服务器',
                self.shutdown_server_from_tray,
                visible=lambda item: self.check_server_status()
            ),
            Menu.SEPARATOR,
            MenuItem('退出', self.quit_app_from_tray)
        )

        self.tray_icon = Icon("Clippy", image, "Clippy", menu)

    def create_icon_image(self, fill_color, outline_color):
        """创建托盘图标图像"""
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, 56, 56], fill=fill_color, outline=outline_color)
        return image

    def update_tray_icon_color(self, connected):
        """更新托盘图标颜色"""
        if self.tray_icon:
            if connected:
                # 绿色 - 已连接
                self.tray_icon.icon = self.create_icon_image('#4CAF50', '#2E7D32')
            else:
                # 红色 - 未连接
                self.tray_icon.icon = self.create_icon_image('#F44336', '#C62828')

    def run_tray_icon(self):
        """在后台线程运行托盘图标"""
        self.tray_icon.run()

    def is_startup_enabled(self):
        """检测开机启动是否已启用"""
        return os.path.exists(self.startup_shortcut)

    def check_server_status(self):
        """检测服务器是否在运行"""
        try:
            response = requests.get(
                f"{self.server_http_url}/ws",
                timeout=1
            )
            return True
        except:
            return False

    def add_to_startup(self):
        """添加到开机启动"""
        try:
            if not os.path.exists(self.vbs_path):
                print(f"警告: VBS启动脚本不存在: {self.vbs_path}")
                return False

            # 使用PowerShell创建快捷方式
            ps_command = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{self.startup_shortcut}')
$Shortcut.TargetPath = '{self.vbs_path}'
$Shortcut.WorkingDirectory = '{self.app_dir}'
$Shortcut.Description = 'Clippy 多端同步剪贴板'
$Shortcut.Save()
"""
            subprocess.run(
                ['powershell', '-Command', ps_command],
                capture_output=True,
                text=True,
                check=True
            )
            print("已添加到开机启动")
            return True
        except Exception as e:
            print(f"添加开机启动失败: {e}")
            return False

    def remove_from_startup(self):
        """从开机启动移除"""
        try:
            if os.path.exists(self.startup_shortcut):
                os.remove(self.startup_shortcut)
                print("已从开机启动移除")
                return True
            return False
        except Exception as e:
            print(f"移除开机启动失败: {e}")
            return False

    def toggle_startup_from_tray(self, icon=None, item=None):
        """切换开机启动状态（从托盘菜单）"""
        if self.is_startup_enabled():
            self.remove_from_startup()
        else:
            self.add_to_startup()
        # 更新托盘菜单
        if self.tray_icon:
            self.tray_icon.update_menu()

    def shutdown_server(self):
        """关闭服务器"""
        try:
            response = requests.post(
                f"{self.server_http_url}/shutdown",
                timeout=2
            )
            if response.status_code == 200:
                print("服务器关闭请求已发送")
                return True
        except Exception as e:
            print(f"关闭服务器失败: {e}")
        return False

    def start_server(self):
        """启动服务器"""
        try:
            server_exe = os.path.join(self.app_dir, 'server.exe')
            if not os.path.exists(server_exe):
                print(f"服务器程序不存在: {server_exe}")
                return False

            # 使用subprocess.Popen在后台启动服务器
            subprocess.Popen(
                [server_exe],
                cwd=self.app_dir,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            print("服务器已启动")
            return True
        except Exception as e:
            print(f"启动服务器失败: {e}")
            return False

    def start_server_from_tray(self, icon=None, item=None):
        """从托盘菜单启动服务器"""
        print("正在启动服务器...")
        # 启用自动重连
        self.auto_reconnect = True
        if self.start_server():
            # 等待服务器启动
            time.sleep(1)
            # 连接WebSocket
            self.connect_websocket()
            # 更新托盘菜单
            if self.tray_icon:
                self.tray_icon.update_menu()
            print("服务器启动完成")

    def shutdown_server_from_tray(self, icon=None, item=None):
        """从托盘菜单关闭服务器"""
        print("正在关闭服务器...")
        # 禁用自动重连
        self.auto_reconnect = False
        # 关闭WebSocket连接
        if self.ws:
            self.ws.close()
        # 关闭服务器
        if self.shutdown_server():
            # 更新图标为红色
            self.update_tray_icon_color(False)
            self.server_connected = False
            # 更新托盘菜单
            if self.tray_icon:
                self.tray_icon.update_menu()
            print("服务器已关闭")

    def restart_server_from_tray(self, icon=None, item=None):
        """重启服务器（从托盘菜单）"""
        print("正在重启服务器...")
        # 启用自动重连
        self.auto_reconnect = True
        # 关闭服务器
        if self.ws:
            self.ws.close()
        if self.shutdown_server():
            # 等待服务器关闭
            time.sleep(1)

        # 启动服务器
        if self.start_server():
            # 等待服务器启动
            time.sleep(1)
            # 重新连接WebSocket
            self.connect_websocket()
            # 更新托盘菜单
            if self.tray_icon:
                self.tray_icon.update_menu()
            print("服务器重启完成")

    def show_popup_from_tray(self, icon=None, item=None):
        """从托盘菜单显示窗口"""
        self.message_queue.put(("show_popup", None))

    def quit_app_from_tray(self, icon=None, item=None):
        """从托盘菜单退出"""
        self.message_queue.put(("quit", None))

    def show_popup(self):
        """显示弹窗"""
        if not self.popup_window:
            self.create_popup_window()

        if self.current_text:
            self.popup_window.deiconify()
            self.popup_window.lift()
            self.popup_window.attributes('-topmost', True)
            self.popup_window.after(100, lambda: self.popup_window.attributes('-topmost', False))

    def hide_popup(self):
        """隐藏弹窗"""
        if self.popup_window:
            self.popup_window.withdraw()

    def on_closing(self):
        """窗口关闭事件"""
        self.quit_app()

    def quit_app(self):
        """退出应用"""
        if self.ws:
            self.ws.close()
        if self.tray_icon:
            self.tray_icon.stop()
        if self.window:
            self.window.quit()

    def update_text_widget(self, text):
        """更新文本显示"""
        if not self.popup_window:
            self.create_popup_window()

        if self.text_widget:
            self.text_widget.config(state='normal')
            self.text_widget.delete(1.0, tk.END)
            self.text_widget.insert(1.0, text)
            self.text_widget.config(state='disabled')

    def copy_text(self):
        """复制文本到剪贴板"""
        if self.current_text:
            pyperclip.copy(self.current_text)
            print("已复制到剪贴板")

    def clear_text(self):
        """清空文本并发送清空消息"""
        self.send_message({"type": "clear"})
        self.hide_popup()

    def send_message(self, message):
        """发送WebSocket消息"""
        if self.ws:
            try:
                self.ws.send(json.dumps(message))
            except Exception as e:
                print(f"发送消息失败: {e}")

    def on_message(self, ws, message):
        """处理接收到的消息（WebSocket线程）"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            content = data.get("content", "")

            print(f"收到消息: type={msg_type}, content={content}")

            # 通过消息队列传递给主线程
            if msg_type == "update":
                if content == "":
                    self.message_queue.put(("hide_popup", None))
                else:
                    self.message_queue.put(("update_text", content))
            elif msg_type == "clear":
                self.message_queue.put(("hide_popup", None))
            elif msg_type == "connected":
                print(f"连接确认: {content}")

        except Exception as e:
            print(f"处理消息错误: {e}")

    def on_error(self, ws, error):
        """处理WebSocket错误"""
        print(f"WebSocket错误: {error}")
        self.server_connected = False
        # 更新托盘图标为红色
        self.update_tray_icon_color(False)
        # 更新托盘菜单
        if self.tray_icon:
            self.tray_icon.update_menu()

    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭"""
        print(f"WebSocket连接关闭: {close_status_code} - {close_msg}")
        self.server_connected = False
        # 更新托盘图标为红色
        self.update_tray_icon_color(False)
        # 更新托盘菜单
        if self.tray_icon:
            self.tray_icon.update_menu()

        # 只有在允许自动重连时才重连
        if self.auto_reconnect:
            print(f"将在 {self.reconnect_delay} 秒后重连...")
            time.sleep(self.reconnect_delay)
            self.connect_websocket()
        else:
            print("自动重连已禁用，不会重连")

    def on_open(self, ws):
        """WebSocket连接建立"""
        print("已连接到服务器")
        self.server_connected = True
        # 更新托盘图标为绿色
        self.update_tray_icon_color(True)
        # 更新托盘菜单
        if self.tray_icon:
            self.tray_icon.update_menu()

    def connect_websocket(self):
        """连接WebSocket服务器"""
        try:
            self.ws = websocket.WebSocketApp(
                self.server_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )

            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()

        except Exception as e:
            print(f"连接失败: {e}")
            time.sleep(self.reconnect_delay)
            self.connect_websocket()

    def process_queue(self):
        """处理消息队列（主线程）"""
        try:
            while not self.message_queue.empty():
                action, data = self.message_queue.get_nowait()

                if action == "update_text":
                    self.current_text = data
                    self.update_text_widget(data)
                    self.show_popup()
                elif action == "hide_popup":
                    self.current_text = ""
                    self.hide_popup()
                elif action == "show_popup":
                    self.show_popup()
                elif action == "quit":
                    self.quit_app()
                    return

        except Exception as e:
            print(f"处理队列错误: {e}")

        # 每100ms检查一次队列
        if self.window:
            self.window.after(100, self.process_queue)

    def run(self):
        """运行应用"""
        # 创建主窗口（tkinter必须在主线程）
        self.create_main_window()

        # 创建并在后台线程运行托盘图标
        self.create_tray_icon()
        tray_thread = threading.Thread(target=self.run_tray_icon)
        tray_thread.daemon = True
        tray_thread.start()

        # 连接WebSocket
        self.connect_websocket()

        # 启动消息队列处理
        self.window.after(100, self.process_queue)

        # 运行tkinter主循环（阻塞）
        self.window.mainloop()


if __name__ == "__main__":
    app = ClippyDesktop()
    app.run()
