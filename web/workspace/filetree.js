export function renderFileTree(items, container) {
  container.innerHTML = '';
  const list = document.createElement('ul');
  items.forEach((item) => list.appendChild(createTreeNode(item)));
  container.appendChild(list);
}

function createTreeNode(item) {
  const node = document.createElement('li');
  node.dataset.path = item.path;
  node.dataset.type = item.type;

  const label = document.createElement('span');
  label.className = item.type;
  label.textContent = `${item.type === 'folder' ? '📁' : '📄'} ${item.name}`;
  node.appendChild(label);

  if (item.type === 'folder' && item.children?.length) {
    const children = document.createElement('ul');
    children.style.display = 'none';
    item.children.forEach((child) => children.appendChild(createTreeNode(child)));
    node.appendChild(children);
    label.addEventListener('click', (event) => {
      event.stopPropagation();
      const expanded = children.style.display !== 'none';
      children.style.display = expanded ? 'none' : 'block';
      label.textContent = `${expanded ? '📁' : '📂'} ${item.name}`;
    });
  }
  return node;
}
