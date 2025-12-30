package protocol

import (
	"encoding/json"
	"time"
)

// MessageType 定义消息类型
type MessageType string

const (
	// MessageTypeUpdate 更新文本
	MessageTypeUpdate MessageType = "update"
	// MessageTypeClear 清空文本
	MessageTypeClear MessageType = "clear"
	// MessageTypeConnected 连接确认
	MessageTypeConnected MessageType = "connected"
)

// Message WebSocket消息结构
type Message struct {
	Type      MessageType `json:"type"`
	Content   string      `json:"content,omitempty"`
	Timestamp int64       `json:"timestamp,omitempty"`
}

// NewUpdateMessage 创建更新消息
func NewUpdateMessage(content string) *Message {
	return &Message{
		Type:      MessageTypeUpdate,
		Content:   content,
		Timestamp: time.Now().Unix(),
	}
}

// NewClearMessage 创建清空消息
func NewClearMessage() *Message {
	return &Message{
		Type:      MessageTypeClear,
		Timestamp: time.Now().Unix(),
	}
}

// NewConnectedMessage 创建连接确认消息
func NewConnectedMessage() *Message {
	return &Message{
		Type:      MessageTypeConnected,
		Content:   "Connected to Clippy server",
		Timestamp: time.Now().Unix(),
	}
}

// Marshal 将消息序列化为JSON字节
func (m *Message) Marshal() ([]byte, error) {
	return json.Marshal(m)
}

// Unmarshal 从JSON字节反序列化消息
func Unmarshal(data []byte) (*Message, error) {
	var msg Message
	err := json.Unmarshal(data, &msg)
	if err != nil {
		return nil, err
	}
	return &msg, nil
}

// IsEmpty 判断更新消息内容是否为空
func (m *Message) IsEmpty() bool {
	return m.Type == MessageTypeUpdate && m.Content == ""
}
