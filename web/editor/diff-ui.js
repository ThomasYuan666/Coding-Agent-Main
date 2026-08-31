export function createDiffUI({ panel, send, getRoot }) {
  const main = panel.closest('main');

  function show(changes) {
    panel.hidden = false;
    main?.classList.add('diff-mode');
    panel.innerHTML = '<div class="diff-toolbar"><strong>Pending changes</strong><button data-action="approve">Accept all</button><button data-action="reject">Reject all</button></div><div class="diff-tabs"></div><pre class="diff-preview"></pre>';
    const tabs = panel.querySelector('.diff-tabs');
    const preview = panel.querySelector('.diff-preview');

    const render = (change) => {
      tabs.querySelectorAll('button').forEach((button) => {
        button.classList.toggle('active', button.dataset.path === change.path);
      });
      preview.innerHTML = '';
      renderLines(preview, change.lines);
      const firstChange = preview.querySelector('.diff-line.added, .diff-line.removed');
      if (firstChange) requestAnimationFrame(() => {
        preview.scrollTop = Math.max(0, firstChange.offsetTop - preview.clientHeight / 3);
      });
    };

    changes.forEach((change) => {
      const tab = document.createElement('button');
      tab.textContent = change.path;
      tab.dataset.path = change.path;
      tab.onclick = () => render(change);
      tabs.appendChild(tab);
    });
    if (changes.length) render(changes[0]);
    panel.querySelector('[data-action="approve"]').onclick = () => send({ action: 'approve', workspace: getRoot?.() });
    panel.querySelector('[data-action="reject"]').onclick = () => send({ action: 'reject', workspace: getRoot?.() });
  }

  function hide() {
    panel.hidden = true;
    panel.innerHTML = '';
    main?.classList.remove('diff-mode');
  }

  return { show, hide };
}

function prefix(type) {
  return type === 'added' ? '+' : type === 'removed' ? '-' : ' ';
}

function renderLines(container, lines, context = 3) {
  const normalized = lines.map((line) => ({ ...line, type: line.type || 'same' }));
  let index = 0;
  while (index < normalized.length) {
    if (normalized[index].type !== 'same') {
      appendLine(container, normalized[index]);
      index += 1;
      continue;
    }
    const start = index;
    while (index < normalized.length && normalized[index].type === 'same') index += 1;
    const count = index - start;
    if (count <= context * 2) {
      for (let line = start; line < index; line += 1) appendLine(container, normalized[line]);
    } else {
      for (let line = start; line < start + context; line += 1) appendLine(container, normalized[line]);
      appendHidden(container, count - context * 2);
      for (let line = index - context; line < index; line += 1) appendLine(container, normalized[line]);
    }
  }
}

function appendLine(container, line) {
  const row = document.createElement('div');
  row.className = `diff-line ${line.type}`;
  row.textContent = `${prefix(line.type)} ${line.text}`;
  container.appendChild(row);
}

function appendHidden(container, count) {
  const row = document.createElement('div');
  row.className = 'diff-unchanged';
  row.textContent = `${count} unchanged line${count === 1 ? '' : 's'}`;
  container.appendChild(row);
}
