export function createTaskUI({ panel, toggle }) {
  let tasks = [];
  toggle.onclick = () => panel.classList.toggle('visible');
  function render(next = tasks) {
    tasks = next;
    panel.innerHTML = '';
    tasks.forEach((task) => {
      const card = document.createElement('details');
      card.className = 'task-card';
      card.open = task.status !== 'completed';
      const summary = document.createElement('summary');
      summary.textContent = `${task.goal} · ${task.status}`;
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
      panel.appendChild(card);
    });
  }
  return { render, update(task) {
    if (!task?.task_id) return;
    const index = tasks.findIndex((item) => item.task_id === task.task_id);
    if (index < 0) tasks.push(task); else tasks[index] = task;
    render();
  }};
}
