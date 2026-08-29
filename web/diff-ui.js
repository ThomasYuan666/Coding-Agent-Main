export function createDiffUI({ panel, send }) {
  function show(changes) {
    panel.hidden = false;
    panel.innerHTML = '<div class="diff-toolbar"><strong>Pending changes</strong><button data-action="approve">Accept all</button><button data-action="reject">Reject all</button></div><div class="diff-tabs"></div><pre class="diff-preview"></pre>';
    const tabs = panel.querySelector('.diff-tabs');
    const preview = panel.querySelector('.diff-preview');

    const render = (change) => {
      tabs.querySelectorAll('button').forEach((button) => {
        button.classList.toggle('active', button.dataset.path === change.path);
      });
      preview.innerHTML = '';
      change.lines.forEach((line) => {
        const row = document.createElement('div');
        row.className = `diff-line ${line.type}`;
        row.textContent = `${prefix(line.type)} ${line.text}`;
        preview.appendChild(row);
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
    panel.querySelector('[data-action="approve"]').onclick = () => send({ action: 'approve' });
    panel.querySelector('[data-action="reject"]').onclick = () => send({ action: 'reject' });
  }

  function hide() {
    panel.hidden = true;
    panel.innerHTML = '';
  }

  return { show, hide };
}

function prefix(type) {
  return type === 'added' ? '+' : type === 'removed' ? '-' : ' ';
}
