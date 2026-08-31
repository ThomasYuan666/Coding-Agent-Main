import { workspaceName, sameWorkspace } from '../workspace/workspace-utils.js';

export function createEditor({ textarea, filename, tabs, getRoot }) {
  const editor = CodeMirror.fromTextArea(textarea, { lineNumbers: true, lineWrapping: false, indentUnit: 4, tabSize: 4, extraKeys: { 'Ctrl-S': save, 'Cmd-S': save } });
  const workspaces = new Map();
  let currentWorkspace = '', activePath = '';
  const state = () => { if (!workspaces.has(currentWorkspace)) workspaces.set(currentWorkspace, { files: new Map(), active: '' }); return workspaces.get(currentWorkspace); };
  function setWorkspace(root) {
    currentWorkspace = workspaceName(root);
    const current = state(); activePath = current.active || '';
    editor.setValue(activePath && current.files.has(activePath) ? current.files.get(activePath) : '');
    editor.clearHistory();
    filename.textContent = activePath || '未选择文件'; renderTabs();
  }
  function loadFile(data) {
    if (data.workspace && !sameWorkspace(data.workspace, currentWorkspace)) return;
    const current = state(); activePath = data.path; current.active = activePath; current.files.set(activePath, data.content);
    editor.setOption('mode', modeFor(activePath)); editor.setValue(data.content); editor.clearHistory(); filename.textContent = activePath; renderTabs();
  }
  function activate(path) {
    const current = state(); current.files.set(activePath, editor.getValue()); activePath = path; current.active = path;
    editor.setOption('mode', modeFor(path)); editor.setValue(current.files.get(path) || ''); editor.clearHistory(); filename.textContent = path; renderTabs();
  }
  function renderTabs() {
    if (!tabs) return; tabs.innerHTML = '';
    state().files.forEach((_, path) => { const button = document.createElement('button'); button.className = path === activePath ? 'active' : ''; button.textContent = path; button.onclick = () => activate(path); tabs.appendChild(button); });
  }
  function save() {
    if (!currentWorkspace || !activePath) return;
    const content = editor.getValue(); state().files.set(activePath, content);
    fetch('/api/file', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ root: getRoot(), path: activePath, content }) });
  }
  return { loadFile, setWorkspace, hasActive: () => Boolean(activePath), getActivePath: () => activePath };
}
function modeFor(path) {
  const ext = path.split('.').pop().toLowerCase();
  return ({ py: 'python', js: 'javascript', jsx: 'javascript', ts: 'javascript', tsx: 'javascript', c: 'text/x-csrc', h: 'text/x-csrc', cpp: 'text/x-c++src', hpp: 'text/x-c++src', java: 'text/x-java', html: 'xml', htm: 'xml', css: 'css', md: 'markdown' })[ext] || null;
}
