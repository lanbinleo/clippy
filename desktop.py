import json
import threading
import time
import tkinter as tk
from tkinter import scrolledtext
from queue import Queue
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import websocket
import pyperclip
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw


class ClippyDesktop:
    def __init__(self):
        self.server_url = "ws://localhost:8948/ws"
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
        # 创建透明背景的图标
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, 56, 56], fill='#4CAF50', outline='#2E7D32')

        menu = Menu(
            MenuItem('显示窗口', self.show_popup_from_tray),
            MenuItem('退出', self.quit_app_from_tray)
        )

        self.tray_icon = Icon("Clippy", image, "Clippy", menu)

    def run_tray_icon(self):
        """在后台线程运行托盘图标"""
        self.tray_icon.run()

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

    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭"""
        print(f"WebSocket连接关闭: {close_status_code} - {close_msg}")
        print(f"将在 {self.reconnect_delay} 秒后重连...")
        time.sleep(self.reconnect_delay)
        self.connect_websocket()

    def on_open(self, ws):
        """WebSocket连接建立"""
        print("已连接到服务器")

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
