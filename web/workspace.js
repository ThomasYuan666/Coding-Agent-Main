/**
 * 工作区管理模块
 */

import { connect, send } from './websocket.js';

let currentRoot = null;

/**
 * 获取当前工作区根目录
 */
export function getCurrentRoot() {
  return currentRoot;
}

/**
 * 初始化工作区（连接 WebSocket，自动接收工作区信息）
 */
export function initWorkspace() {
  // 连接 WebSocket，服务器会自动发送固定工作区的信息
  connect();
}

/**
 * 打开文件（发送读取请求）
 * @param {string} path - 文件相对路径
 */
export function openFile(path) {
  send({ action: 'read', path });
}
