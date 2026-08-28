/**
 * 文件树渲染模块
 */

import { openFile } from './workspace.js';

/**
 * 渲染文件树
 * @param {Array} files - 文件树数据
 * @param {HTMLElement} container - 容器元素
 */
export function renderFileTree(files, container) {
  container.innerHTML = '';
  const ul = document.createElement('ul');
  files.forEach(item => {
    ul.appendChild(createTreeNode(item));
  });
  container.appendChild(ul);
}

/**
 * 创建树节点
 * @param {Object} item - 文件或文件夹对象
 * @returns {HTMLElement} 列表项元素
 */
function createTreeNode(item) {
  const li = document.createElement('li');
  li.dataset.path = item.path;
  li.dataset.type = item.type;

  if (item.type === 'folder') {
    // 文件夹
    const span = document.createElement('span');
    span.textContent = `📁 ${item.name}`;
    span.className = 'folder';
    li.appendChild(span);

    // 子节点容器
    if (item.children && item.children.length > 0) {
      const childUl = document.createElement('ul');
      childUl.style.display = 'none'; // 默认折叠
      item.children.forEach(child => {
        childUl.appendChild(createTreeNode(child));
      });
      li.appendChild(childUl);

      // 点击展开/折叠
      span.onclick = (e) => {
        e.stopPropagation();
        const isExpanded = childUl.style.display !== 'none';
        childUl.style.display = isExpanded ? 'none' : 'block';
        span.textContent = `${isExpanded ? '📁' : '📂'} ${item.name}`;
      };
    }
  } else {
    // 文件
    const span = document.createElement('span');
    span.textContent = `📄 ${item.name}`;
    span.className = 'file';
    span.onclick = () => openFile(item.path);
    li.appendChild(span);
  }

  return li;
}
