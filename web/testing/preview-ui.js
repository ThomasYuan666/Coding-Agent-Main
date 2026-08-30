import { workspaceName } from '../workspace/workspace-utils.js';

export function createPreviewUI({ panel }) {
  const urls = new Map();
  let currentWorkspace = '';

  function show(workspace, url) {
    const key = workspaceName(workspace);
    if (!key || !url) return;
    urls.set(key, url);
    if (key !== currentWorkspace) return;
    panel.hidden = false;
    panel.replaceChildren();
    const toolbar = document.createElement('div');
    toolbar.className = 'preview-toolbar';
    const title = document.createElement('strong');
    title.textContent = '网页预览';
    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = '关闭';
    close.onclick = hide;
    toolbar.append(title, close);
    const frame = document.createElement('iframe');
    frame.src = url;
    frame.title = '网页预览';
    panel.append(toolbar, frame);
  }
  function hide(workspace) {
    if (workspace) urls.delete(workspaceName(workspace));
    panel.hidden = true;
    panel.replaceChildren();
  }

  function setWorkspace(workspace) {
    currentWorkspace = workspaceName(workspace);
    const url = urls.get(currentWorkspace);
    if (url) show(currentWorkspace, url);
    else hide();
  }

  return { show, hide, setWorkspace };
}
