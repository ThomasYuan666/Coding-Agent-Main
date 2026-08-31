import { connect, send, onMessage } from './core/websocket.js';
import { createChatUI } from './chat/chat-ui.js?v=31';
import { createDiffUI } from './editor/diff-ui.js?v=3';
import { createEditor } from './editor/editor-ui.js';
import { createWorkspaceUI } from './workspace/workspace-ui.js?v=18';
import { createTaskUI } from './tasks/task-ui.js?v=20';

const files = document.querySelector('#files');
const messages = document.querySelector('#messages');
const editorElement = document.querySelector('#editor');
let workspaceUI;
const taskUI = createTaskUI({
  panel: document.querySelector('#task-panel'),
  toggle: document.querySelector('#agent-orb'),
  main: document.querySelector('main'),
  onWorkspace: (root) => openWorkspace(root),
  onAgentPanel: () => diffUI?.hide()
});

workspaceUI = createWorkspaceUI({
  files,
  title: document.querySelector('#workspace'),
  send,
  onOpen: (root) => enterWorkspace(root)
});
const editorUI = createEditor({
  textarea: editorElement,
  filename: document.querySelector('#filename'),
  tabs: document.querySelector('#editor-tabs'),
  getRoot: workspaceUI.getRoot
});
const chatUI = createChatUI({
  messages,
  input: document.querySelector('#input'),
  modelSelect: document.querySelector('#model-select'),
  reasoningSelect: document.querySelector('#reasoning-select'),
  compactButton: document.querySelector('#compact-context'),
  imageStatus: document.querySelector('#image-status'),
  imagePreview: document.querySelector('#image-preview'),
  contextStatus: document.querySelector('#context-status'),
  contextRing: document.querySelector('#context-ring'),
  form: document.querySelector('#chat'),
  sendButton: document.querySelector('#send'),
  getRoot: workspaceUI.getRoot,
  send
});
const diffUI = createDiffUI({
  panel: document.querySelector('#diff-panel'),
  send,
  getRoot: workspaceUI.getRoot
});

onMessage((data) => {
  const currentEvent = !data.workspace || workspaceUI.isCurrent(data.workspace);
  if (currentEvent) chatUI.handle(data);
  if (data.type === 'root_set') {
    send({ action: 'files' });
  }
  if (data.type === 'container') {
    workspaceUI.renderContainer(data.files);
    taskUI.setWorkspaces(data.files);
  }
  if (data.type === 'files' && (!data.workspace || workspaceUI.isCurrent(data.workspace))) {
    workspaceUI.refresh(data.files);
    if (!editorUI.hasActive()) {
      const path = workspaceUI.firstFile();
      if (path) send({ action: 'read', path });
    }
  }
  if (currentEvent && data.type === 'diff') diffUI.show(data.files);
  if (currentEvent && data.type === 'diff_status') diffUI.hide();
  if (currentEvent && data.type === 'file_content') editorUI.loadFile(data);
  if (data.type === 'tasks') taskUI.render(data.tasks);
  if (data.type === 'task_update' && data.task) {
    data.task.workspace = data.workspace;
    taskUI.update(data.task);
  }
  if (data.type === 'workspace_statuses') {
    data.items.forEach((item) => workspaceUI.setStatus(item.workspace, item.status));
  }
  if (data.type === 'agent_status') {
    workspaceUI.setStatus(data.workspace, data.status);
    taskUI.updateStatus(data.workspace, data.status, data.task_id);
  }
});

function openWorkspace(root, notify = true) {
  workspaceUI.open(root, notify);
}

function enterWorkspace(root) {
  diffUI.hide();
  editorUI.setWorkspace(root);
  chatUI.setWorkspace(root);
  taskUI.render();
}

const connection = connect();
connection.addEventListener('open', () => send({ action: 'set_container' }), { once: true });
