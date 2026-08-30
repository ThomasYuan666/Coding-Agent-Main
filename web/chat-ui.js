export function createChatUI({ messages, input, modelSelect, reasoningSelect, imageStatus, contextStatus, contextRing, compactButton, form, sendButton, getRoot, send }) {
  let liveSegment = null;
  let pendingImage = null;
  const busyByWorkspace = new Map();

  function workspaceKey() {
    return getRoot() || '__none__';
  }

  function isBusy() {
    return Boolean(busyByWorkspace.get(workspaceKey()));
  }

  if (compactButton) {
    compactButton.onclick = () => {
      if (!getRoot() || isBusy()) return;
      compactButton.disabled = true;
      send({ action: 'compact' });
    };
  }

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
    if (type === 'reasoning' || type === 'tool') {
      makeCollapsible(item, type === 'tool' && label !== '需要确认');
    }
    if (type === 'user' && turnId && canRollback) addRollbackButton(item, turnId);
    messages.scrollTop = messages.scrollHeight;
    return content;
  }

  function makeCollapsible(item, collapsed = false) {
    item.classList.add('collapsible');
    if (collapsed) item.classList.add('collapsed');
    const header = item.querySelector('strong');
    header.setAttribute('role', 'button');
    header.tabIndex = 0;
    const toggle = () => item.classList.toggle('collapsed');
    header.onclick = toggle;
    header.onkeydown = (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        toggle();
      }
    };
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
      if (message.reasoning_content) {
        const reasoning = addMessage('reasoning', '思考', message.reasoning_content);
        reasoning.parentElement.classList.add('collapsed');
      }
      if (message.role === 'assistant' && message.content) addMessage('agent', 'Agent', message.content, true);
      (message.tool_calls || []).forEach((call) => {
        const fn = call.function || {};
        addMessage('tool', `工具：${fn.name || 'unknown'}`, `参数：${fn.arguments || '{}'}`);
      });
      if (message.role === 'tool') addMessage('tool', '工具结果', message.content || '');
    });
  }

  function appendLiveSegment(type, text) {
    if (liveSegment && liveSegment.dataset.type !== type) collapseThinking();
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
    busyByWorkspace.set(workspaceKey(), value);
    sendButton.disabled = false;
    sendButton.textContent = value ? '停止' : '发送';
    sendButton.classList.toggle('busy', value);
  }

  function collapseThinking() {
    const item = liveSegment?.parentElement;
    if (item?.classList.contains('reasoning')) item.classList.add('collapsed');
  }

  function handle(data) {
    if (data.type === 'history') {
      renderHistory(data.messages, data.rollback_turn_ids);
      return;
    }
    if (data.type === 'context_usage' && contextStatus) {
      const tokens = data.usage?.prompt_tokens;
      const limit = data.limit;
      if (Number.isFinite(tokens) && Number.isFinite(limit) && limit > 0) {
        const percent = Math.min(100, Math.round(tokens / limit * 100));
        contextStatus.textContent = `上下文 ${tokens.toLocaleString()} tokens`;
        if (contextRing) {
          contextRing.style.setProperty('--usage', `${percent * 3.6}deg`);
          contextRing.querySelector('span').textContent = `${percent}%`;
        }
      }
    }
    if (data.type === 'context_status' && contextStatus) {
      contextStatus.textContent = data.status === 'compacting' ? '正在压缩上下文...' : '上下文已更新';
      if (compactButton) compactButton.disabled = data.status === 'compacting';
    }
    if (data.type === 'rollback_state') updateRollbackButtons(data.turn_ids);
    if (data.type === 'user' && data.turn_id) addMessage('user', '你', data.content, false, data.turn_id, true);
    if (data.type === 'reasoning') appendLiveSegment('reasoning', data.content);
    if (data.type === 'start') liveSegment = null;
    if (data.type === 'chunk') appendLiveSegment('content', data.content);
    if (data.type === 'approval') renderApproval(data);
    if (data.type === 'end' || data.type === 'stopped') {
      collapseThinking();
      liveSegment = null;
      setBusy(false);
    }
    if (data.type === 'error') {
      addMessage('tool', '错误', data.content);
      if (compactButton) compactButton.disabled = false;
    }
    if (data.type === 'tool') {
      collapseThinking();
      liveSegment = null;
      collapsePendingToolCards();
      addMessage('tool', `工具：${data.tool}`, data.result);
    }
    if (data.type === 'tool_call') {
      collapseThinking();
      liveSegment = null;
      const toolCall = addMessage('tool', `工具：${data.tool}`, `等待审批\n参数：${data.arguments || '{}'}`);
      const card = toolCall.parentElement;
      card.classList.remove('collapsed');
      card.dataset.pendingTool = 'true';
    }
  }

  function renderApproval(data) {
    collapseThinking();
    liveSegment = null;
    const block = addMessage('tool', '需要确认', `${data.reason}\n${data.command}`);
    const card = block.parentElement;
    const actions = document.createElement('div');
    actions.className = 'approval-actions';
    ['approve', 'reject'].forEach((action) => {
      const button = document.createElement('button');
      button.textContent = action === 'approve' ? '允许' : '拒绝';
      button.onclick = () => {
        actions.textContent = action === 'approve' ? '已允许，正在执行...' : '已拒绝，正在通知 Agent...';
        collapsePendingToolCards();
        card.classList.add('collapsed');
        send({ action, workspace: data.workspace, task_id: data.task_id });
      };
      actions.appendChild(button);
    });
    block.parentElement.appendChild(actions);
  }

  function collapsePendingToolCards() {
    messages.querySelectorAll('.msg.tool[data-pending-tool]').forEach((item) => {
      item.classList.add('collapsed');
      delete item.dataset.pendingTool;
    });
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
    if (isBusy()) {
      send({ action: 'stop' });
      return;
    }
    if (!getRoot()) return;
    const text = input.value.trim();
    if (!text && !pendingImage) return;
    const content = pendingImage
      ? [{ type: 'text', text }, { type: 'image_url', image_url: { url: pendingImage, detail: 'auto' } }]
      : text;
    send({ action: 'message', content, model: modelSelect.value, reasoning_effort: reasoningSelect.value });
    input.value = '';
    pendingImage = null;
    imageStatus.textContent = '';
    setBusy(true);
  };

  return { handle, setWorkspace: (root) => {
    if (!root) return;
    busyByWorkspace.set(root, Boolean(busyByWorkspace.get(root)));
    setBusy(Boolean(busyByWorkspace.get(root)));
  }};
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
