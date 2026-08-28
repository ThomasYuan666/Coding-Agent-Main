import { connect, send, onMessage } from './websocket.js';
import { renderFileTree } from './filetree.js';

const ROOT = 'workspace';
const files = document.querySelector('#files');
const messages = document.querySelector('#messages');
const editor = document.querySelector('#editor');
const input = document.querySelector('#input');
let currentRoot = '';
let reply;

function add(type, label, text = '') {
  const el = document.createElement('div');
  el.className = `msg ${type}`;
  el.innerHTML = `<strong>${label}</strong><span></span>`;
  el.querySelector('span').textContent = text;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
  return el.querySelector('span');
}

function loadWorkspace(name) {
  currentRoot = `${ROOT}\\${name}`;
  document.querySelector('#workspace').textContent = `当前工作区：${name}`;
  document.querySelectorAll('#files li.folder').forEach((item) => item.classList.toggle('active', item.dataset.path === name));
  messages.innerHTML = '';
  send({ action: 'set_root', root: currentRoot });
}

onMessage((data) => {
  if (data.type === 'container') renderFileTree(data.files, files);
  if (data.type === 'root_set') document.querySelector('#workspace').textContent = `当前工作区：${data.root.split('\\').pop()}`;
  if (data.type === 'files') renderFileTree(data.files, files);
  if (data.type === 'file_content') { document.querySelector('#filename').textContent = data.path; editor.value = data.content; editor.dataset.path = data.path; }
  if (data.type === 'history') { messages.innerHTML = ''; data.messages.filter((m) => m.role !== 'system').forEach((m) => add(m.role === 'user' ? 'user' : 'agent', m.role === 'user' ? '你' : 'Agent', m.content)); }
  if (data.type === 'user') add('user', '你', data.content);
  if (data.type === 'start') reply = add('agent', 'Agent');
  if (data.type === 'chunk' && reply) { reply.textContent += data.content; messages.scrollTop = messages.scrollHeight; }
  if (data.type === 'end') reply = null;
  if (data.type === 'tool') add('tool', `工具：${data.tool}`, data.result);
  if (data.type === 'approval') { const block = add('tool', '需要确认', `${data.reason}\n${data.command}`); block.innerHTML += ' <button data-a="approve">允许</button><button data-a="reject">拒绝</button>'; block.querySelectorAll('button').forEach((b) => { b.onclick = () => send({ action: b.dataset.a }); }); }
});

const connection = connect();
if (connection.readyState === WebSocket.OPEN) {
  send({ action: 'set_container' });
} else {
  connection.addEventListener('open', () => send({ action: 'set_container' }), { once: true });
}
files.addEventListener('click', (event) => {
  const item = event.target.closest('li');
  if (item?.dataset.type === 'folder' && item.parentElement === files.querySelector('ul')) {
    loadWorkspace(item.dataset.path);
  }
}, true);
editor.onkeydown = (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); fetch('/api/file', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ root: currentRoot, path: editor.dataset.path, content: editor.value }) }); } };
document.querySelector('#chat').onsubmit = (e) => { e.preventDefault(); if (input.value.trim() && currentRoot) { send({ action: 'message', content: input.value.trim() }); input.value = ''; } };
