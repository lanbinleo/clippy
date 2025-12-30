package main

import (
	"clippy/pkg/protocol"
	"context"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		return true // 允许所有来源
	},
}

// Hub 管理所有客户端连接
type Hub struct {
	clients    map[*Client]bool
	broadcast  chan *protocol.Message
	register   chan *Client
	unregister chan *Client
	mu         sync.RWMutex
}

// Client 代表一个WebSocket客户端
type Client struct {
	hub  *Hub
	conn *websocket.Conn
	send chan *protocol.Message
}

// NewHub 创建新的Hub
func NewHub() *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		broadcast:  make(chan *protocol.Message, 256),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

// Run 启动Hub
func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			log.Printf("Client connected. Total clients: %d", len(h.clients))
			// 发送连接确认消息
			client.send <- protocol.NewConnectedMessage()

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()
			log.Printf("Client disconnected. Total clients: %d", len(h.clients))

		case message := <-h.broadcast:
			h.mu.RLock()
			for client := range h.clients {
				select {
				case client.send <- message:
				default:
					// 如果客户端的发送通道已满，断开连接
					close(client.send)
					delete(h.clients, client)
				}
			}
			h.mu.RUnlock()
		}
	}
}

// readPump 从WebSocket读取消息
func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	for {
		_, data, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("WebSocket error: %v", err)
			}
			break
		}

		// 解析消息
		msg, err := protocol.Unmarshal(data)
		if err != nil {
			log.Printf("Failed to unmarshal message: %v", err)
			continue
		}

		log.Printf("Received message: type=%s, content=%s", msg.Type, msg.Content)

		// 广播消息给所有客户端
		c.hub.broadcast <- msg
	}
}

// writePump 向WebSocket写入消息
func (c *Client) writePump() {
	defer func() {
		c.conn.Close()
	}()

	for {
		message, ok := <-c.send
		if !ok {
			// Hub关闭了通道
			c.conn.WriteMessage(websocket.CloseMessage, []byte{})
			return
		}

		data, err := message.Marshal()
		if err != nil {
			log.Printf("Failed to marshal message: %v", err)
			continue
		}

		err = c.conn.WriteMessage(websocket.TextMessage, data)
		if err != nil {
			log.Printf("Failed to write message: %v", err)
			return
		}
	}
}

// handleWebSocket 处理WebSocket连接
func handleWebSocket(hub *Hub, w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("Failed to upgrade connection: %v", err)
		return
	}

	client := &Client{
		hub:  hub,
		conn: conn,
		send: make(chan *protocol.Message, 256),
	}

	hub.register <- client

	// 启动读写协程
	go client.writePump()
	go client.readPump()
}

// handleShutdown 处理关闭服务器请求
func handleShutdown(srv *http.Server) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		log.Println("Shutdown request received")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("Server shutting down..."))

		// 异步关闭服务器
		go func() {
			time.Sleep(500 * time.Millisecond) // 给响应时间返回
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()

			if err := srv.Shutdown(ctx); err != nil {
				log.Printf("Server shutdown error: %v", err)
				os.Exit(1)
			}
			log.Println("Server stopped gracefully")
			os.Exit(0)
		}()
	}
}

func main() {
	hub := NewHub()
	go hub.Run()

	mux := http.NewServeMux()

	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		handleWebSocket(hub, w, r)
	})

	// 创建服务器实例
	srv := &http.Server{
		Addr:    ":8948",
		Handler: mux,
	}

	// 添加关闭端点
	mux.HandleFunc("/shutdown", handleShutdown(srv))

	log.Println("Clippy server starting on :8948")
	log.Println("Endpoints: /ws (WebSocket), /shutdown (HTTP POST)")

	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal("ListenAndServe error: ", err)
	}
}
