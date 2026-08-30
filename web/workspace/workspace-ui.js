import { renderFileTree } from './filetree.js';
import { workspaceName, sameWorkspace } from './workspace-utils.js';

export function createWorkspaceUI({ files, title, send, onOpen }) {
  const rootName = 'workspace';
  let currentRoot = '';
  const statuses = new Map();

  function refresh(tree) {
    if (!currentRoot) return;
    const item = findCurrentItem();
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

  function findCurrentItem() {
    const name = workspaceName(currentRoot);
    return [...files.querySelectorAll(':scope > ul > li[data-type="folder"]')]
      .find((node) => node.dataset.path === name);
  }

  function restoreSelection() {
    const current = findCurrentItem();
    files.querySelectorAll(':scope > ul > li[data-type="folder"]').forEach((item) => {
      const selected = item === current;
      item.classList.toggle('active', selected);
      item.classList.toggle('expanded', selected);
      const children = item.querySelector(':scope > ul');
      if (children) children.style.display = selected ? 'block' : 'none';
    });
  }

  function open(nameOrRoot, notify = true) {
    const name = workspaceName(nameOrRoot);
    if (!name) return;
    currentRoot = `${rootName}\\${name}`;
    title.textContent = `当前工作区：${name}`;
    restoreSelection();
    if (notify) send({ action: 'set_root', root: currentRoot });
    onOpen?.(currentRoot);
  }

  function setStatus(root, status) {
    const name = workspaceName(root);
    statuses.set(name, status);
    const item = [...files.querySelectorAll(':scope > ul > li[data-type="folder"]')]
      .find((node) => node.dataset.path === name);
    if (!item) return;
    item.dataset.agentStatus = status;
    item.classList.toggle('agent-running', status === 'running');
    item.classList.toggle('agent-waiting', status === 'waiting_approval');
    item.classList.toggle('agent-failed', status === 'failed');
    item.classList.toggle('agent-completed', status === 'completed');
  }

  function firstFile() {
    const item = findCurrentItem();
    const file = item?.querySelector('li[data-type="file"]');
    if (!file) return '';
    const prefix = `${workspaceName(currentRoot)}\\`;
    return file.dataset.path.startsWith(prefix) ? file.dataset.path.slice(prefix.length) : file.dataset.path;
  }

  files.addEventListener('click', (event) => {
    const item = event.target.closest('li');
    if (!item) return;
    if (item.dataset.type === 'folder' && item.parentElement === files.querySelector('ul')) {
      event.stopImmediatePropagation();
      open(item.dataset.path);
      return;
    }
    if (item.dataset.type === 'file' && currentRoot) {
      event.stopImmediatePropagation();
      const prefix = `${workspaceName(currentRoot)}\\`;
      const path = item.dataset.path.startsWith(prefix)
        ? item.dataset.path.slice(prefix.length)
        : item.dataset.path;
      send({ action: 'read', path });
    }
  }, true);

  return {
    renderContainer: (tree) => {
      renderFileTree(tree, files);
      restoreSelection();
      statuses.forEach((status, name) => setStatus(`${rootName}\\${name}`, status));
    },
    refresh,
    open,
    setStatus,
    isCurrent: (workspace) => sameWorkspace(workspace, currentRoot),
    firstFile,
    getRoot: () => currentRoot
  };
}
