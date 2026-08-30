/**
 * WebSocket 连接管理模块
 */

let ws = null;
let messageHandlers = [];

/**
 * 注册消息处理器
 * @param {Function} handler - 处理函数 (data) => void
 */
export function onMessage(handler) {
  messageHandlers.push(handler);
}

/**
 * 连接 WebSocket
 */
export function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    return ws;
  }

  ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = () => {
    console.log('WebSocket 已连接');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      messageHandlers.forEach(handler => handler(data));
    } catch (e) {
      console.error('解析消息失败:', e);
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket 错误:', error);
  };

  ws.onclose = () => {
    console.log('WebSocket 已断开');
    ws = null;
  };

  return ws;
}

/**
 * 发送消息
 * @param {Object} data - 要发送的数据
 */
export function send(data) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.error('WebSocket 未连接');
    return false;
  }
  ws.send(JSON.stringify(data));
  return true;
}
