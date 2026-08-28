let root = "", socket, current = {}, generating = false;
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
  if (generating) return;
  const text = $('input').value.trim();
  if (!text) return;

  generating = true;
  $('input').disabled = true;
  $('send').disabled = true;
  $('stop').style.display = 'inline-block';

  const el = document.createElement('div');
  el.className = 'msg user';
  el.innerHTML = `<strong>User</strong><span>${text}</span>`;
  $('messages').appendChild(el);
  $('input').value = '';
  current = {};

  socket.send(JSON.stringify({ root, content: text }));
  scroll();
}

function stopGeneration() {
  if (!generating) return;
  socket.send(JSON.stringify({ action: 'stop', root }));
}

function revertMessage() {
  if (generating) return;
  socket.send(JSON.stringify({ action: 'revert', root }));
  const messages = $('messages');
  if (messages.children.length >= 2) {
    messages.removeChild(messages.lastChild);
    messages.removeChild(messages.lastChild);
  }
}

function append(type, text) {
  const key = type === 'reasoning' ? 'reason' : 'content';
  const label = type === 'reasoning' ? '思考中...' : 'Agent';
  const msgClass = type === 'reasoning' ? 'reasoning' : 'agent';

  if (!current[key]) {
    const el = document.createElement('div');
    el.className = `msg ${msgClass}`;
    el.innerHTML = `<strong>${label}</strong><span></span>`;
    $('messages').appendChild(el);
    current[key] = el.querySelector('span');

    if (type === 'reasoning') {
      el.querySelector('strong').onclick = () => el.classList.toggle('collapsed');
    }
  }

  current[key].textContent += text;
  scroll();
}

function buildTree(files) {
  const tree = {};
  files.forEach(path => {
    const parts = path.split(/[\\/]/);
    let node = tree;
    parts.forEach((part, i) => {
      if (i === parts.length - 1) {
        if (!node._files) node._files = [];
        node._files.push({ name: part, path });
      } else {
        if (!node[part]) node[part] = {};
        node = node[part];
      }
    });
  });
  return tree;
}

function renderTree(node, indent = 0) {
  let html = '';
  const folders = Object.keys(node).filter(k => k !== '_files').sort();
  const files = node._files || [];

  folders.forEach(folder => {
    html += `<li class="folder" style="padding-left:${indent * 15}px" data-folder="${folder}">📁 ${folder}</li>`;
    html += `<ul style="display:none;">${renderTree(node[folder], indent + 1)}</ul>`;
  });

  files.sort((a, b) => a.name.localeCompare(b.name)).forEach(file => {
    html += `<li class="file" style="padding-left:${indent * 15}px" data-path="${file.path}">📄 ${file.name}</li>`;
  });

  return html;
}

async function files() {
  const list = await (await fetch('/api/files?path=' + encodeURIComponent(root))).json();
  const tree = buildTree(list);
  $('files').innerHTML = renderTree(tree);

  document.querySelectorAll('#files .folder').forEach(item => {
    item.onclick = () => {
      const content = item.nextElementSibling;
      if (content && content.tagName === 'UL') {
        const isOpen = content.style.display !== 'none';
        content.style.display = isOpen ? 'none' : 'block';
        item.textContent = (isOpen ? '📁 ' : '📂 ') + item.dataset.folder;
      }
    };
  });

  document.querySelectorAll('#files .file').forEach(item => {
    item.onclick = () => openFile(item.dataset.path);
  });
}

async function openFile(path) {
  $('filename').textContent = path;
  $('editor').value = await (await fetch('/api/file?root=' + encodeURIComponent(root) + '&path=' + encodeURIComponent(path))).text();
  $('editor').dataset.path = path;
}

async function initWorkspace(workspacePath) {
  root = workspacePath;
  $('workspace').textContent = workspacePath.split(/[\\/]/).pop();

  if (socket) socket.close();
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

    if (data.type === 'done' || data.type === 'stopped') {
      generating = false;
      $('input').disabled = false;
      $('send').disabled = false;
      $('stop').style.display = 'none';
      files();
    }

    if (data.type === 'reverted') {
      // UI already updated in revertMessage()
    }
  };

  await files();

  const history = await (await fetch('/api/history?root=' + encodeURIComponent(root))).json();
  $('messages').innerHTML = '';
  history.filter(m => m.role === 'user' || (m.role === 'assistant' && m.content)).forEach(m => {
    const label = m.role === 'user' ? '你' : 'Agent';
    const type = m.role === 'user' ? 'user' : 'agent';
    block(type, label).textContent = m.content;
  });
}

$('open').onclick = async () => {
  const data = await (await fetch('/api/workspace')).json();
  if (!data.path) return;
  await initWorkspace(data.path);
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
  startReply();
};

$('input').onkeydown = event => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    $('chat').onsubmit(event);
  }
};

const recentPanel = document.createElement('section');
recentPanel.className = 'recent-panel';
recentPanel.innerHTML = '<h4>最近打开</h4><div id="recent-list"></div>';
document.querySelector('aside').appendChild(recentPanel);

async function refreshRecent() {
  const list = await (await fetch('/api/recent')).json();
  const listEl = document.getElementById('recent-list');
  if (!listEl) return;

  listEl.innerHTML = list.map(item =>
    `<div class="recent-item" data-path="${item.path}">
      <span>${item.name}</span>
      <button data-remove="1">×</button>
    </div>`
  ).join('');

  document.querySelectorAll('.recent-item').forEach(item => {
    const removeBtn = item.querySelector('button[data-remove]');

    removeBtn.onclick = async event => {
      event.stopPropagation();
      await fetch('/api/recent?path=' + encodeURIComponent(item.dataset.path), {method:'DELETE'});
      refreshRecent();
    };

    item.onclick = async () => {
      await initWorkspace(item.dataset.path);
    };
  });
}

refreshRecent();
