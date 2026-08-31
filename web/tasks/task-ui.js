import { workspaceName } from '../workspace/workspace-utils.js';

export function createTaskUI({ panel, detailPanel, toggle, main, getRoot, onWorkspace }) {
  let tasks = [];
  const statuses = new Map();
  const taskById = new Map();
  const workspaces = new Set();
  const workspaceRoots = new Map();
  const statusMeta = (status) => ({ running: ['运行中', 'running'], waiting_approval: ['待审批', 'waiting'], failed: ['失败', 'failed'], completed: ['已完成', 'completed'], idle: ['空闲', 'idle'] }[status] || [status || '空闲', 'idle']);
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
      const name = workspaceName(task.workspace);
      workspaces.add(name);
      workspaceRoots.set(name, task.workspace);
    });
    tasks = [...taskById.values()].filter((task) => task.workspace);
    panel.innerHTML = '';
    const groups = new Map();
    tasks.forEach((task) => {
      const key = workspaceName(task.workspace);
      if (!key) return;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(task);
    });
    workspaces.forEach((workspace) => { if (!groups.has(workspace)) groups.set(workspace, []); });
    groups.forEach((workspaceTasks, workspace) => {
      const card = document.createElement('article');
      card.className = 'workspace-card';
      const name = workspaceName(workspace);
      const heading = document.createElement('button');
      heading.className = 'workspace-card-header';
      heading.onclick = () => onWorkspace?.(workspaceRoots.get(workspace) || workspace);
      const [headingLabel, headingClass] = statusMeta(statuses.get(workspace));
      heading.textContent = '';
      const headingName = document.createElement('span');
      headingName.className = 'workspace-card-name';
      headingName.textContent = name;
      const headingStatus = document.createElement('span');
      headingStatus.className = `status-badge status-${headingClass}`;
      headingStatus.textContent = headingLabel;
      heading.append(headingName, headingStatus);
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
    const currentName = workspaceName(root);
    const current = tasks.filter((task) => task.workspace && workspaceName(task.workspace) === currentName);
    current.forEach((task) => {
      const card = document.createElement('details');
      card.className = 'task-card';
      card.open = task.status !== 'completed';
      const summary = document.createElement('summary');
      const runtime = statuses.get(task.workspace) || statuses.get(currentName);
      const [summaryLabel, summaryClass] = statusMeta(runtime || task.status);
      summary.textContent = '';
      const summaryGoal = document.createElement('span');
      summaryGoal.className = 'task-card-goal';
      summaryGoal.textContent = task.goal;
      const summaryStatus = document.createElement('span');
      summaryStatus.className = `status-badge status-${summaryClass}`;
      summaryStatus.textContent = summaryLabel;
      summary.append(summaryGoal, summaryStatus);
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
          block.appendChild(row);
          const marker = document.createElement('span');
          marker.className = 'plan-step-marker';
          marker.textContent = step.status === 'completed' ? '✓' : step.status === 'failed' ? '×' : '•';
          row.textContent = '';
          row.append(marker, document.createTextNode(` ${step.title}`));
        });
        card.appendChild(block);
      });
      detailPanel.appendChild(card);
    });
  }
  return { render, setWorkspaces(items) {
    (items || []).filter((item) => item.type === 'folder').forEach((item) => workspaces.add(workspaceName(item.path)));
    render();
  }, showDashboard, showWorkspace, updateStatus(workspace, status, taskId) {
    if (!workspace) return;
    const normalized = String(workspace).replace(/\//g, '\\');
    const name = workspaceName(normalized);
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
