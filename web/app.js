import { connect, send, onMessage } from './websocket.js';
import { renderFileTree } from './filetree.js';

const ROOT = 'workspace';
const files = document.querySelector('#files');
const messages = document.querySelector('#messages');
const editor = document.querySelector('#editor');
const input = document.querySelector('#input');
const codeEditor = CodeMirror.fromTextArea(editor, {
  lineNumbers: true,
  lineWrapping: false,
  indentUnit: 4,
  tabSize: 4,
  autofocus: false,
  extraKeys: {
    'Ctrl-S': saveCurrentFile,
    'Cmd-S': saveCurrentFile
  }
});
let currentRoot = '';
let liveSegment = null;

function saveCurrentFile() {
  if (!currentRoot || !editor.dataset.path) return;
  fetch('/api/file', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ root: currentRoot, path: editor.dataset.path, content: codeEditor.getValue() })
  });
}

function editorMode(path) {
  const extension = path.split('.').pop().toLowerCase();
  return ({
    py: 'python', js: 'javascript', jsx: 'javascript', ts: 'javascript', tsx: 'javascript',
    c: 'text/x-csrc', h: 'text/x-csrc', cpp: 'text/x-c++src', hpp: 'text/x-c++src',
    java: 'text/x-java', html: 'xml', htm: 'xml', css: 'css', md: 'markdown'
  })[extension] || null;
}

function renderMarkdown(text) {
  if (!window.marked) return text;
  const html = window.marked.parse(text, { breaks: true });
  const safe = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
  if (!window.hljs) return safe;
  const holder = document.createElement('div');
  holder.innerHTML = safe;
  holder.querySelectorAll('pre code').forEach((block) => window.hljs.highlightElement(block));
  return holder.innerHTML;
}

function addMessage(type, label, text = '', markdown = false) {
  const item = document.createElement('div');
  item.className = `msg ${type}`;
  item.innerHTML = `<strong>${label}</strong><span></span>`;
  const content = item.querySelector('span');
  content.dataset.raw = text;
  if (markdown) content.innerHTML = renderMarkdown(text);
  else content.textContent = text;
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  return item.querySelector('span');
}

function appendLiveSegment(type, text) {
  if (!liveSegment || liveSegment.dataset.type !== type) {
    const span = addMessage(type === 'content' ? 'agent' : 'reasoning', type === 'reasoning' ? 'Thinking' : 'Agent', '', type === 'content');
    liveSegment = span;
    liveSegment.dataset.type = type;
  }
  liveSegment.dataset.raw = (liveSegment.dataset.raw || '') + text;
  liveSegment.innerHTML = type === 'content' ? renderMarkdown(liveSegment.dataset.raw) : '';
  if (type === 'reasoning') liveSegment.textContent = liveSegment.dataset.raw;
  messages.scrollTop = messages.scrollHeight;
}

function renderHistory(history) {
  messages.innerHTML = '';
  history.filter((message) => message.role !== 'system').forEach((message) => {
    if (message.role === 'user') addMessage('user', '你', message.content || '');
    if (message.reasoning_content) addMessage('reasoning', '思考', message.reasoning_content);
    if (message.role === 'assistant' && message.content) addMessage('agent', 'Agent', message.content, true);
    (message.tool_calls || []).forEach((call) => {
      const fn = call.function || {};
      addMessage('tool', `工具：${fn.name || 'unknown'}`, `参数：${fn.arguments || '{}'}`);
    });
    if (message.role === 'tool') addMessage('tool', '工具结果', message.content || '');
  });
}

function refreshCurrentWorkspace(tree) {
  if (!currentRoot) return;
  const name = currentRoot.split('\\').pop();
  const workspaceItem = [...files.querySelectorAll(':scope > ul > li[data-type="folder"]')]
    .find((item) => item.dataset.path === name);
  if (!workspaceItem) return;
  const temporary = document.createElement('div');
  renderFileTree(tree, temporary);
  const newChildren = temporary.querySelector(':scope > ul');
  const oldChildren = workspaceItem.querySelector(':scope > ul');
  if (oldChildren) oldChildren.replaceWith(newChildren);
  else workspaceItem.appendChild(newChildren);
  newChildren.style.display = 'block';
  workspaceItem.classList.add('active', 'expanded');
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
  if (data.type === 'history') {
    renderHistory(data.messages);
    return;
  }
  if (data.type === 'container') renderFileTree(data.files, files);
  if (data.type === 'files') refreshCurrentWorkspace(data.files);
  if (data.type === 'root_set') document.querySelector('#workspace').textContent = `当前工作区：${data.root.split('\\').pop()}`;
  if (data.type === 'file_content') {
    document.querySelector('#filename').textContent = data.path;
    editor.dataset.path = data.path;
    codeEditor.setOption('mode', editorMode(data.path));
    codeEditor.setValue(data.content);
    codeEditor.clearHistory();
  }
  if (data.type === 'user') addMessage('user', '你', data.content);
  if (data.type === 'reasoning') appendLiveSegment('reasoning', data.content);
  if (data.type === 'start') { liveSegment = null; }
  if (data.type === 'chunk') {
    appendLiveSegment('content', data.content);
  }
  if (data.type === 'end') liveSegment = null;
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
document.querySelector('#chat').onsubmit = (event) => { event.preventDefault(); const text = input.value.trim(); if (text && currentRoot) { send({ action: 'message', content: text }); input.value = ''; } };
messages.addEventListener('click', (event) => {
  if (event.target.tagName === 'STRONG' && event.target.parentElement.classList.contains('reasoning')) {
    event.target.parentElement.classList.toggle('collapsed');
  }
});
