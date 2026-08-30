import { connect, send, onMessage } from './websocket.js';
import { createChatUI } from './chat-ui.js';
import { createDiffUI } from './diff-ui.js';
import { createEditor } from './editor-ui.js';
import { createWorkspaceUI } from './workspace-ui.js';
import { createTaskUI } from './task-ui.js';

const files = document.querySelector('#files');
const messages = document.querySelector('#messages');
const editorElement = document.querySelector('#editor');
const taskUI = createTaskUI({ panel: document.querySelector('#task-panel'), toggle: document.querySelector('#tasks-toggle') });

const workspaceUI = createWorkspaceUI({
  files,
  title: document.querySelector('#workspace'),
  messages,
  send
});
const editorUI = createEditor({
  textarea: editorElement,
  filename: document.querySelector('#filename'),
  getRoot: workspaceUI.getRoot
});
const chatUI = createChatUI({
  messages,
  input: document.querySelector('#input'),
  modelSelect: document.querySelector('#model-select'),
  reasoningSelect: document.querySelector('#reasoning-select'),
  compactButton: document.querySelector('#compact-context'),
  imageStatus: document.querySelector('#image-status'),
  contextStatus: document.querySelector('#context-status'),
  contextRing: document.querySelector('#context-ring'),
  form: document.querySelector('#chat'),
  sendButton: document.querySelector('#send'),
  getRoot: workspaceUI.getRoot,
  send
});
const diffUI = createDiffUI({
  panel: document.querySelector('#diff-panel'),
  send
});

onMessage((data) => {
  chatUI.handle(data);
  if (data.type === 'container') workspaceUI.renderContainer(data.files);
  if (data.type === 'files') workspaceUI.refresh(data.files);
  if (data.type === 'diff') diffUI.show(data.files);
  if (data.type === 'diff_status') diffUI.hide();
  if (data.type === 'file_content') editorUI.loadFile(data);
  if (data.type === 'tasks') taskUI.render(data.tasks);
  if (data.type === 'task_update') taskUI.update(data.task);
});

const connection = connect();
connection.addEventListener('open', () => send({ action: 'set_container' }), { once: true });
