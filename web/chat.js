/**
 * 聊天消息处理模块
 */

import { send } from './websocket.js';

let messageIndex = 0;
const messagesContainer = document.getElementById('messages');

/**
 * 重置消息索引（切换工作区时调用）
 */
export function resetMessageIndex() {
  messageIndex = 0;
}

/**
 * 创建消息块
 * @param {string} type - 消息类型 (user/agent/tool/diff)
 * @param {string} label - 消息标签
 * @param {number} index - 消息索引
 * @returns {HTMLElement} 消息元素
 */
export function createMessageBlock(type, label, index) {
  const el = document.createElement('div');
  el.className = `msg ${type}`;
  el.dataset.index = index;

  // 创建消息头部
  const header = document.createElement('div');
  header.className = 'msg-header';
  header.innerHTML = `<strong>${label}</strong>`;

  // 为用户和 AI 消息添加回退按钮
  if (type === 'user' || type === 'agent') {
    const revertBtn = document.createElement('button');
    revertBtn.className = 'revert-btn';
    revertBtn.textContent = '↩';
    revertBtn.onclick = () => revertToMessage(index);
    header.appendChild(revertBtn);
  }

  el.appendChild(header);

  // 创建内容容器
  const content = document.createElement('div');
  content.className = 'msg-content';
  el.appendChild(content);

  return el;
}

/**
 * 追加内容到消息块
 * @param {HTMLElement} el - 消息元素
 * @param {string} text - 要追加的文本
 */
export function appendContent(el, text) {
  const content = el.querySelector('.msg-content');
  if (content) {
    content.textContent += text;
  }
}

/**
 * 设置消息内容
 * @param {HTMLElement} el - 消息元素
 * @param {string} text - 内容文本
 */
export function setContent(el, text) {
  const content = el.querySelector('.msg-content');
  if (content) {
    content.textContent = text;
  }
}

/**
 * 添加消息到聊天区域
 * @param {HTMLElement} el - 消息元素
 */
export function addMessage(el) {
  messagesContainer.appendChild(el);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * 获取下一个消息索引
 * @returns {number}
 */
export function getNextIndex() {
  return messageIndex++;
}

/**
 * 显示 diff
 * @param {string} path - 文件路径
 * @param {string} diffText - diff 文本
 */
export function showDiff(path, diffText) {
  const el = createMessageBlock('diff', `📝 文件变更: ${path}`, -1);

  const diffContent = document.createElement('pre');
  diffContent.className = 'diff-content';
  diffContent.textContent = diffText;

  el.querySelector('.msg-content').appendChild(diffContent);
  addMessage(el);
}

/**
 * 回退到指定消息
 * @param {number} index - 消息索引
 */
function revertToMessage(index) {
  if (!confirm('确定要回退到此消息吗？之后的所有消息将被删除。')) {
    return;
  }

  // 发送回退请求到服务器
  send({ action: 'revert', index });

  // 删除 DOM 中该索引之后的所有消息
  const allMessages = messagesContainer.querySelectorAll('.msg');
  allMessages.forEach(msg => {
    const msgIndex = parseInt(msg.dataset.index);
    if (!isNaN(msgIndex) && msgIndex > index) {
      msg.remove();
    }
  });

  // 重置消息索引
  messageIndex = index + 1;
}

/**
 * 发送用户消息
 * @param {string} text - 消息文本
 */
export function sendMessage(text) {
  if (!text.trim()) return;

  send({
    action: 'message',
    content: text
  });
}

/**
 * 清空聊天区域
 */
export function clearMessages() {
  messagesContainer.innerHTML = '';
  resetMessageIndex();
}
