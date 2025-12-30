package main

import (
	"clippy/pkg/protocol"
	"log"
	"time"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/driver/desktop"
	"fyne.io/fyne/v2/layout"
	"fyne.io/fyne/v2/widget"
	"github.com/gorilla/websocket"
)

const serverURL = "ws://localhost:8948/ws"

type ClippyApp struct {
	app        fyne.App
	window     fyne.Window
	textWidget *widget.Entry
	conn       *websocket.Conn
	sendChan   chan *protocol.Message
}

func NewClippyApp() *ClippyApp {
	a := app.NewWithID("com.clippy.desktop")
	w := a.NewWindow("Clippy")

	// 窗口初始隐藏
	w.Hide()

	// 设置窗口大小
	w.Resize(fyne.NewSize(400, 200))

	return &ClippyApp{
		app:      a,
		window:   w,
		sendChan: make(chan *protocol.Message, 10),
	}
}

func (ca *ClippyApp) setupUI() {
	// 创建多行文本显示区域
	ca.textWidget = widget.NewMultiLineEntry()
	ca.textWidget.Wrapping = fyne.TextWrapWord
	ca.textWidget.Disable() // 只读

	// 复制按钮
	copyBtn := widget.NewButton("复制", func() {
		ca.window.Clipboard().SetContent(ca.textWidget.Text)
		log.Println("Text copied to clipboard")
	})

	// 清空按钮
	clearBtn := widget.NewButton("清空", func() {
		ca.sendChan <- protocol.NewClearMessage()
		ca.window.Hide()
		log.Println("Clear message sent")
	})

	// 按钮布局
	btnContainer := container.New(
		layout.NewGridLayout(2),
		copyBtn,
		clearBtn,
	)

	// 主容器
	content := container.NewBorder(
		nil,
		btnContainer,
		nil,
		nil,
		container.NewScroll(ca.textWidget),
	)

	ca.window.SetContent(content)

	// 设置窗口关闭处理（隐藏而不是退出）
	ca.window.SetCloseIntercept(func() {
		ca.window.Hide()
	})
}

func (ca *ClippyApp) setupTray() {
	if desk, ok := ca.app.(desktop.App); ok {
		menu := fyne.NewMenu("Clippy",
			fyne.NewMenuItem("显示窗口", func() {
				ca.window.Show()
			}),
			fyne.NewMenuItemSeparator(),
			fyne.NewMenuItem("退出", func() {
				ca.disconnect()
				ca.app.Quit()
			}),
		)
		desk.SetSystemTrayMenu(menu)
	}
}

func (ca *ClippyApp) connectWebSocket() error {
	var err error
	ca.conn, _, err = websocket.DefaultDialer.Dial(serverURL, nil)
	if err != nil {
		return err
	}

	log.Println("Connected to server:", serverURL)

	// 启动读写协程
	go ca.readLoop()
	go ca.writeLoop()

	return nil
}

func (ca *ClippyApp) disconnect() {
	if ca.conn != nil {
		ca.conn.Close()
	}
	close(ca.sendChan)
}

func (ca *ClippyApp) readLoop() {
	defer func() {
		ca.conn.Close()
	}()

	for {
		_, data, err := ca.conn.ReadMessage()
		if err != nil {
			log.Printf("Read error: %v", err)
			// 尝试重连
			ca.reconnect()
			return
		}

		msg, err := protocol.Unmarshal(data)
		if err != nil {
			log.Printf("Unmarshal error: %v", err)
			continue
		}

		ca.handleMessage(msg)
	}
}

func (ca *ClippyApp) writeLoop() {
	for msg := range ca.sendChan {
		data, err := msg.Marshal()
		if err != nil {
			log.Printf("Marshal error: %v", err)
			continue
		}

		err = ca.conn.WriteMessage(websocket.TextMessage, data)
		if err != nil {
			log.Printf("Write error: %v", err)
			return
		}
	}
}

func (ca *ClippyApp) handleMessage(msg *protocol.Message) {
	log.Printf("Received message: type=%s, content=%s", msg.Type, msg.Content)

	switch msg.Type {
	case protocol.MessageTypeUpdate:
		if msg.IsEmpty() {
			// 内容为空，隐藏窗口
			ca.window.Hide()
		} else if msg.Content != "" {
			// 有内容，显示窗口
			ca.textWidget.SetText(msg.Content)
			ca.window.Show()
			// 将窗口移到右下角
			ca.positionWindowBottomRight()
		}

	case protocol.MessageTypeClear:
		// 清空消息，隐藏窗口
		ca.window.Hide()

	case protocol.MessageTypeConnected:
		log.Println("Connection confirmed:", msg.Content)
	}
}

func (ca *ClippyApp) positionWindowBottomRight() {
	// 获取屏幕尺寸
	screen := fyne.CurrentApp().Driver().AllWindows()[0].Canvas().Size()
	windowSize := ca.window.Canvas().Size()

	// 计算右下角位置（留出一些边距）
	x := screen.Width - windowSize.Width - 20
	y := screen.Height - windowSize.Height - 60

	ca.window.CenterOnScreen()
	// 注意：Fyne v2没有直接设置窗口位置的API，CenterOnScreen是最接近的
	// 如果需要精确定位，可能需要使用其他方法或等待Fyne更新
}

func (ca *ClippyApp) reconnect() {
	log.Println("Attempting to reconnect...")
	for {
		time.Sleep(5 * time.Second)
		err := ca.connectWebSocket()
		if err == nil {
			log.Println("Reconnected successfully")
			return
		}
		log.Printf("Reconnect failed: %v, retrying...", err)
	}
}

func main() {
	ca := NewClippyApp()
	ca.setupUI()
	ca.setupTray()

	// 连接WebSocket
	err := ca.connectWebSocket()
	if err != nil {
		log.Printf("Failed to connect to server: %v", err)
		log.Println("Will retry in background...")
		go ca.reconnect()
	}

	ca.app.Run()
}
