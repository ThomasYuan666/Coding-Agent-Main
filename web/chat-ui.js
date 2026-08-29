export function createChatUI({ messages, input, modelSelect, imageStatus, form, sendButton, getRoot, send }) {
  let liveSegment = null;
  let pendingImage = null;
  let busy = false;

  function addMessage(type, label, text = '', markdown = false, turnId = '', canRollback = false) {
    const item = document.createElement('div');
    item.className = `msg ${type}`;
    if (turnId) item.dataset.turnId = turnId;
    item.innerHTML = `<strong>${label}</strong><span></span>`;
    const content = item.querySelector('span');
    content.dataset.raw = typeof text === 'string' ? text : '';
    if (Array.isArray(text)) {
      text.forEach((part) => {
        if (part.type === 'text') content.appendChild(document.createTextNode(part.text));
        if (part.type === 'image_url' && part.image_url?.url) {
          const image = document.createElement('img');
          image.src = part.image_url.url;
          image.alt = '用户粘贴的图片';
          image.className = 'message-image';
          content.appendChild(image);
        }
      });
    } else if (markdown) {
      content.innerHTML = renderMarkdown(text);
    } else {
      content.textContent = text;
    }
    messages.appendChild(item);
    if (type === 'user' && turnId && canRollback) addRollbackButton(item, turnId);
    messages.scrollTop = messages.scrollHeight;
    return content;
  }

  function addRollbackButton(item, turnId) {
    if (item.querySelector('.rollback-button')) return;
    const button = document.createElement('button');
    button.className = 'rollback-button';
    button.textContent = '回退此回合';
    button.onclick = () => send({ action: 'rollback', turn_id: turnId });
    item.appendChild(button);
  }

  function updateRollbackButtons(turnIds) {
    const available = new Set(turnIds || []);
    messages.querySelectorAll('.msg.user').forEach((item) => {
      const turnId = item.dataset.turnId;
      const button = item.querySelector('.rollback-button');
      if (turnId && available.has(turnId)) addRollbackButton(item, turnId);
      else if (button) button.remove();
    });
  }

  function renderHistory(history, rollbackTurnIds = []) {
    messages.innerHTML = '';
    history.filter((message) => message.role !== 'system').forEach((message) => {
      if (message.role === 'user') {
        addMessage('user', '你', message.content || '', false, message.turn_id || '', rollbackTurnIds.includes(message.turn_id));
      }
      if (message.reasoning_content) addMessage('reasoning', '思考', message.reasoning_content);
      if (message.role === 'assistant' && message.content) addMessage('agent', 'Agent', message.content, true);
      (message.tool_calls || []).forEach((call) => {
        const fn = call.function || {};
        addMessage('tool', `工具：${fn.name || 'unknown'}`, `参数：${fn.arguments || '{}'}`);
      });
      if (message.role === 'tool') addMessage('tool', '工具结果', message.content || '');
    });
  }

  function appendLiveSegment(type, text) {
    if (!liveSegment || liveSegment.dataset.type !== type) {
      liveSegment = addMessage(
        type === 'content' ? 'agent' : 'reasoning',
        type === 'reasoning' ? 'Thinking' : 'Agent',
        '',
        type === 'content'
      );
      liveSegment.dataset.type = type;
    }
    liveSegment.dataset.raw = (liveSegment.dataset.raw || '') + text;
    if (type === 'content') liveSegment.innerHTML = renderMarkdown(liveSegment.dataset.raw);
    else liveSegment.textContent = liveSegment.dataset.raw;
    messages.scrollTop = messages.scrollHeight;
  }

  function setBusy(value) {
    busy = value;
    sendButton.disabled = value;
  }

  function handle(data) {
    if (data.type === 'history') {
      renderHistory(data.messages, data.rollback_turn_ids);
      return;
    }
    if (data.type === 'rollback_state') updateRollbackButtons(data.turn_ids);
    if (data.type === 'user' && data.turn_id) addMessage('user', '你', data.content, false, data.turn_id, true);
    if (data.type === 'reasoning') appendLiveSegment('reasoning', data.content);
    if (data.type === 'start') liveSegment = null;
    if (data.type === 'chunk') appendLiveSegment('content', data.content);
    if (data.type === 'approval') renderApproval(data);
    if (data.type === 'end') { liveSegment = null; setBusy(false); }
    if (data.type === 'error') addMessage('tool', '错误', data.content);
    if (data.type === 'tool') addMessage('tool', `工具：${data.tool}`, data.result);
    if (data.type === 'tool_call') {
      addMessage('tool', `工具：${data.tool}`, `等待审批\n参数：${data.arguments || '{}'}`);
    }
  }

  function renderApproval(data) {
    liveSegment = null;
    const block = addMessage('tool', '需要确认', `${data.reason}\n${data.command}`);
    const actions = document.createElement('div');
    actions.className = 'approval-actions';
    ['approve', 'reject'].forEach((action) => {
      const button = document.createElement('button');
      button.textContent = action === 'approve' ? '允许' : '拒绝';
      button.onclick = () => {
        actions.textContent = action === 'approve' ? '已允许，正在执行...' : '已拒绝，正在通知 Agent...';
        send({ action });
      };
      actions.appendChild(button);
    });
    block.parentElement.appendChild(actions);
  }

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  input.addEventListener('paste', (event) => {
    const image = [...(event.clipboardData?.items || [])].find((item) => item.type.startsWith('image/'));
    if (!image) return;
    const file = image.getAsFile();
    if (!file || file.size > 32 * 1024 * 1024) {
      imageStatus.textContent = '图片超过 32 MiB';
      return;
    }
    event.preventDefault();
    const reader = new FileReader();
    reader.onload = () => {
      pendingImage = reader.result;
      imageStatus.textContent = `已粘贴图片 (${Math.round(file.size / 1024)} KiB)`;
    };
    reader.readAsDataURL(file);
  });

  form.onsubmit = (event) => {
    event.preventDefault();
    if (busy || !getRoot()) return;
    const text = input.value.trim();
    if (!text && !pendingImage) return;
    const content = pendingImage
      ? [{ type: 'text', text }, { type: 'image_url', image_url: { url: pendingImage, detail: 'auto' } }]
      : text;
    send({ action: 'message', content, model: modelSelect.value });
    input.value = '';
    pendingImage = null;
    imageStatus.textContent = '';
    setBusy(true);
  };

  messages.addEventListener('click', (event) => {
    if (event.target.tagName === 'STRONG' && event.target.parentElement.classList.contains('reasoning')) {
      event.target.parentElement.classList.toggle('collapsed');
    }
  });

  return { handle };
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
