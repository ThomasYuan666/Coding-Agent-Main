export function createTaskUI({ panel, detailPanel, toggle, main, getRoot, onWorkspace }) {
  let tasks = [];
  const statuses = new Map();
  const taskById = new Map();
  const workspaces = new Set();
  const workspaceRoots = new Map();
  function showDashboard() {
    panel.classList.add('visible');
    main?.classList.add('dashboard-mode');
  }

  function showWorkspace() {
    panel.classList.remove('visible');
    main?.classList.remove('dashboard-mode');
  }

  toggle.onclick = showDashboard;
  function render(next = tasks) {
    next.filter((task) => task && task.task_id).forEach((task) => {
      if (!task.workspace) return;
      task.workspace = String(task.workspace).replace(/\//g, '\\');
      taskById.set(task.task_id, task);
      const name = task.workspace.split('\\').filter(Boolean).pop();
      workspaces.add(name);
      workspaceRoots.set(name, task.workspace);
    });
    tasks = [...taskById.values()].filter((task) => task.workspace);
    panel.innerHTML = '';
    const groups = new Map();
    tasks.forEach((task) => {
      const key = task.workspace ? task.workspace.split('\\').filter(Boolean).pop() : '';
      if (!key) return;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(task);
    });
    workspaces.forEach((workspace) => { if (!groups.has(workspace)) groups.set(workspace, []); });
    groups.forEach((workspaceTasks, workspace) => {
      const card = document.createElement('article');
      card.className = 'workspace-card';
      const name = workspace.split('\\').pop();
      const heading = document.createElement('button');
      heading.className = 'workspace-card-header';
      heading.textContent = `${name} · ${statuses.get(workspace) || 'idle'}`;
      heading.onclick = () => onWorkspace?.(workspaceRoots.get(workspace) || workspace);
      card.appendChild(heading);
      const latest = workspaceTasks[workspaceTasks.length - 1];
      const taskSummary = document.createElement('div');
      taskSummary.className = 'workspace-card-task';
      taskSummary.textContent = latest?.goal || '暂无任务';
      card.appendChild(taskSummary);
      panel.appendChild(card);
    });
    renderDetails();
  }

  function renderDetails() {
    if (!detailPanel) return;
    detailPanel.innerHTML = '';
    const root = getRoot?.();
    const currentName = root ? root.split('\\').pop() : '';
    const current = tasks.filter((task) => task.workspace && task.workspace.split('\\').pop() === currentName);
    current.forEach((task) => {
      const card = document.createElement('details');
      card.className = 'task-card';
      card.open = task.status !== 'completed';
      const summary = document.createElement('summary');
      const runtime = statuses.get(task.workspace) || statuses.get(currentName);
      summary.textContent = `${task.workspace ? task.workspace.split('\\').pop() + ' · ' : ''}${task.goal} · ${runtime || task.status}`;
      card.appendChild(summary);
      (task.plans || []).forEach((plan) => {
        const block = document.createElement('details');
        block.className = 'plan-block';
        block.open = plan.status !== 'completed';
        const heading = document.createElement('summary');
        heading.textContent = plan.goal;
        block.appendChild(heading);
        (plan.steps || []).forEach((step) => {
          const row = document.createElement('div');
          row.className = `plan-step ${step.status}`;
          row.textContent = `${step.status === 'completed' ? '✓' : step.status === 'failed' ? '×' : '○'} ${step.title}`;
          block.appendChild(row);
        });
        card.appendChild(block);
      });
      detailPanel.appendChild(card);
    });
  }
  return { render, setWorkspaces(items) {
    (items || []).filter((item) => item.type === 'folder').forEach((item) => workspaces.add(item.path.split('\\').filter(Boolean).pop()));
    render();
  }, showDashboard, showWorkspace, updateStatus(workspace, status, taskId) {
    if (!workspace) return;
    const normalized = String(workspace).replace(/\//g, '\\');
    const name = normalized.split('\\').filter(Boolean).pop();
    statuses.set(normalized, status);
    statuses.set(name, status);
    workspaces.add(name);
    const task = tasks.find((item) => item.task_id === taskId);
    if (task) task.workspace = workspace;
    render();
  }, update(task) {
    if (!task?.task_id) return;
    if (!task.workspace) return;
    task.workspace = String(task.workspace).replace(/\//g, '\\');
    const index = tasks.findIndex((item) => item.task_id === task.task_id);
    if (index < 0) tasks.push(task); else tasks[index] = task;
    render();
  }};
}
