# Clippy - 多端同步剪贴板工具

通过手机语音输入，实时同步到电脑端剪贴板的工具。

## 项目结构

```
Clippy/
├── server.exe          # Go后端服务器（已编译）
├── desktop.py          # Python桌面客户端
├── requirements.txt    # Python依赖
├── API.md             # API文档
└── cmd/               # Go源代码
    ├── server/        # 服务器源码
    └── desktop/       # Fyne桌面端源码（未使用）
```

## 快速开始

### 1. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务器

```bash
server.exe
```

服务器将在 `localhost:8948` 启动。

### 3. 启动桌面客户端

```bash
python desktop.py
```

桌面客户端会：
- 最小化到系统托盘（绿色圆圈图标）
- 自动连接到本地服务器
- 等待手机端消息

### 4. 手机端开发

参考 `API.md` 文档，连接到：
```
ws://你的电脑IP:8948/ws
```

发送消息格式：
```json
{
  "type": "update",
  "content": "语音输入的文字"
}
```

## 使用流程

1. **手机语音输入** → 发送 `update` 消息到服务器
2. **电脑端弹窗** → 在屏幕右下角显示文本
3. **点击"复制"** → 文本复制到剪贴板，窗口保持显示
4. **点击"清空"** → 发送 `clear` 消息，窗口隐藏

## 功能特性

- ✅ WebSocket实时通信
- ✅ 系统托盘图标
- ✅ 右下角弹窗显示
- ✅ 一键复制到剪贴板
- ✅ 自动重连
- ✅ 无需鉴权（局域网使用）

## 技术栈

- **后端**: Go + gorilla/websocket
- **桌面端**: Python + tkinter + ttkbootstrap
- **通信**: WebSocket (JSON格式)

## 注意事项

- 确保防火墙允许 8948 端口
- 手机和电脑需在同一局域网
- 详细API文档见 `API.md`

## 开发计划

- [ ] 添加连接密码保护
- [ ] 支持文本历史记录
- [ ] 添加配置文件
- [ ] 打包为单一可执行文件
