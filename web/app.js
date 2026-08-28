import { connect, send, onMessage } from './websocket.js';
import { renderFileTree } from './filetree.js';

const ROOT = 'workspace';
const files = document.querySelector('#files');
const messages = document.querySelector('#messages');
const editor = document.querySelector('#editor');
const input = document.querySelector('#input');
let currentRoot = '';
let reply = null;

function addMessage(type, label, text = '') {
  const item = document.createElement('div');
  item.className = `msg ${type}`;
  item.innerHTML = `<strong>${label}</strong><span></span>`;
  item.querySelector('span').textContent = text;
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item.querySelector('span');
}

function selectWorkspace(name) {
  currentRoot = `${ROOT}\\${name}`;
  document.querySelector('#workspace').textContent = `当前工作区：${name}`;
  document.querySelectorAll('#files > ul > li[data-type="folder"]').forEach((item) => {
    const selected = item.dataset.path === name;
    item.classList.toggle('active', selected);
    item.classList.toggle('expanded', selected);
    const children = item.querySelector(':scope > ul');
    if (children) children.style.display = selected ? 'block' : 'none';
  });
  messages.innerHTML = '';
  send({ action: 'set_root', root: currentRoot });
}

onMessage((data) => {
  if (data.type === 'container') renderFileTree(data.files, files);
  if (data.type === 'root_set') document.querySelector('#workspace').textContent = `当前工作区：${data.root.split('\\').pop()}`;
  if (data.type === 'file_content') { document.querySelector('#filename').textContent = data.path; editor.value = data.content; editor.dataset.path = data.path; }
  if (data.type === 'history') { messages.innerHTML = ''; data.messages.filter((m) => m.role !== 'system').forEach((m) => addMessage(m.role === 'user' ? 'user' : 'agent', m.role === 'user' ? '你' : 'Agent', m.content)); }
  if (data.type === 'user') addMessage('user', '你', data.content);
  if (data.type === 'start') reply = addMessage('agent', 'Agent');
  if (data.type === 'chunk' && reply) { reply.textContent += data.content; messages.scrollTop = messages.scrollHeight; }
  if (data.type === 'end') reply = null;
  if (data.type === 'tool') addMessage('tool', `工具：${data.tool}`, data.result);
  if (data.type === 'approval') { const block = addMessage('tool', '需要确认', `${data.reason}\n${data.command}`); block.innerHTML += ' <button data-a="approve">允许</button><button data-a="reject">拒绝</button>'; block.querySelectorAll('button').forEach((button) => { button.onclick = () => send({ action: button.dataset.a }); }); }
});

const connection = connect();
connection.addEventListener('open', () => send({ action: 'set_container' }), { once: true });
files.addEventListener('click', (event) => {
  const item = event.target.closest('li');
  if (!item) return;
  if (item.dataset.type === 'folder' && item.parentElement === files.querySelector('ul')) {
    selectWorkspace(item.dataset.path);
    return;
  }
  if (item.dataset.type === 'file' && currentRoot) {
    event.stopImmediatePropagation();
    const prefix = `${currentRoot.split('\\').pop()}\\`;
    const path = item.dataset.path.startsWith(prefix) ? item.dataset.path.slice(prefix.length) : item.dataset.path;
    send({ action: 'read', path });
  }
}, true);
editor.onkeydown = (event) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); fetch('/api/file', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ root: currentRoot, path: editor.dataset.path, content: editor.value }) }); } };
document.querySelector('#chat').onsubmit = (event) => { event.preventDefault(); const text = input.value.trim(); if (text && currentRoot) { send({ action: 'message', content: text }); input.value = ''; } };
