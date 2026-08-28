let root = "", socket, current = {};
const $ = id => document.getElementById(id);

function scroll() {
  const messages = $('messages');
  messages.scrollTop = messages.scrollHeight;
}

function block(type, label) {
  const el = document.createElement('div');
  el.className = `msg ${type}`;
  el.innerHTML = `<strong>${label}</strong><span></span>`;
  $('messages').appendChild(el);
  scroll();
  return el.querySelector('span');
}

function startReply() {
  current = {};
}

function append(type, text) {
  // 为 reasoning 和 content 分别创建独立的消息块
  const key = type === 'reasoning' ? 'reason' : 'content';
  const label = type === 'reasoning' ? '思考中...' : 'Agent';
  const msgClass = type === 'reasoning' ? 'reasoning' : 'agent';

  if (!current[key]) {
    const el = document.createElement('div');
    el.className = `msg ${msgClass}`;
    el.innerHTML = `<strong>${label}</strong><span></span>`;
    $('messages').appendChild(el);
    current[key] = el.querySelector('span');
  }

  current[key].textContent += text;
  scroll();
}

async function files() {
  const list = await (await fetch('/api/files?path=' + encodeURIComponent(root))).json();
  $('files').innerHTML = list.map(p => `<li data-p="${p}">${p}</li>`).join('');
  document.querySelectorAll('#files li').forEach(item => item.onclick = () => openFile(item.dataset.p));
}

async function openFile(path) {
  $('filename').textContent = path;
  $('editor').value = await (await fetch('/api/file?root=' + encodeURIComponent(root) + '&path=' + encodeURIComponent(path))).text();
  $('editor').dataset.path = path;
}

$('open').onclick = async () => {
  const data = await (await fetch('/api/workspace')).json();
  if (!data.path) return;
  root = data.path;
  $('workspace').textContent = data.name;

  socket = new WebSocket(`ws://${location.host}/ws`);
  socket.onmessage = event => {
    const data = JSON.parse(event.data);

    if (data.type === 'reasoning' || data.type === 'content') {
      append(data.type, data.text);
    }

    if (data.type === 'tool') {
      const el = block('tool', `工具: ${data.tool}`);
      el.textContent = data.result;
    }

    if (data.type === 'confirm') {
      const el = block('tool', '需要确认');
      el.innerHTML = `工具 <strong>${data.tool}</strong> 需要执行 <button data-ok="1">✓ 允许</button> <button data-ok="0">✗ 拒绝</button>`;
      el.querySelectorAll('button').forEach(b => b.onclick = () => {
        socket.send(JSON.stringify({ approved: b.dataset.ok === '1' }));
        el.parentElement.style.opacity = '0.6';
      });
    }

    if (data.type === 'done') {
      files();
    }
  };

  await files();

  const history = await (await fetch('/api/history?root=' + encodeURIComponent(root))).json();
  history.filter(m => m.role === 'user' || (m.role === 'assistant' && m.content)).forEach(m => {
    const label = m.role === 'user' ? '你' : 'Agent';
    const type = m.role === 'user' ? 'user' : 'agent';
    block(type, label).textContent = m.content;
  });
};

$('editor').onkeydown = event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    event.preventDefault();
    fetch('/api/file', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ root, path: $('editor').dataset.path, content: $('editor').value })
    });
  }
};

$('chat').onsubmit = event => {
  event.preventDefault();
  const text = $('input').value.trim();
  if (!text || !socket) return;

  block('user', '你').textContent = text;
  startReply();
  socket.send(JSON.stringify({ root, content: text }));
  $('input').value = '';
};
