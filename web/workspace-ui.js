import { renderFileTree } from './filetree.js';

export function createWorkspaceUI({ files, title, messages, send }) {
  const rootName = 'workspace';
  let currentRoot = '';

  function refresh(tree) {
    if (!currentRoot) return;
    const name = currentRoot.split('\\').pop();
    const item = [...files.querySelectorAll(':scope > ul > li[data-type="folder"]')]
      .find((node) => node.dataset.path === name);
    if (!item) return;
    const temporary = document.createElement('div');
    renderFileTree(tree, temporary);
    const children = temporary.querySelector(':scope > ul');
    const oldChildren = item.querySelector(':scope > ul');
    if (oldChildren) oldChildren.replaceWith(children);
    else item.appendChild(children);
    children.style.display = 'block';
    item.classList.add('active', 'expanded');
  }

  function select(name) {
    currentRoot = `${rootName}\\${name}`;
    title.textContent = `当前工作区：${name}`;
    files.querySelectorAll(':scope > ul > li[data-type="folder"]').forEach((item) => {
      const selected = item.dataset.path === name;
      item.classList.toggle('active', selected);
      item.classList.toggle('expanded', selected);
      const children = item.querySelector(':scope > ul');
      if (children) children.style.display = selected ? 'block' : 'none';
    });
    messages.innerHTML = '';
    send({ action: 'set_root', root: currentRoot });
  }

  files.addEventListener('click', (event) => {
    const item = event.target.closest('li');
    if (!item) return;
    if (item.dataset.type === 'folder' && item.parentElement === files.querySelector('ul')) {
      event.stopImmediatePropagation();
      select(item.dataset.path);
      return;
    }
    if (item.dataset.type === 'file' && currentRoot) {
      event.stopImmediatePropagation();
      const prefix = `${currentRoot.split('\\').pop()}\\`;
      const path = item.dataset.path.startsWith(prefix)
        ? item.dataset.path.slice(prefix.length)
        : item.dataset.path;
      send({ action: 'read', path });
    }
  }, true);

  return {
    renderContainer: (tree) => renderFileTree(tree, files),
    refresh,
    getRoot: () => currentRoot
  };
}
