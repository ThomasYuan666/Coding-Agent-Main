export function workspaceName(root) {
  return String(root || '').replace(/\\/g, '/').split('/').filter(Boolean).pop() || '';
}

export function sameWorkspace(left, right) {
  return Boolean(left && right && workspaceName(left) === workspaceName(right));
}
