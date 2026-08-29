export function createEditor({ textarea, filename, getRoot }) {
  const codeEditor = CodeMirror.fromTextArea(textarea, {
    lineNumbers: true,
    lineWrapping: false,
    indentUnit: 4,
    tabSize: 4,
    autofocus: false,
    extraKeys: {
      'Ctrl-S': save,
      'Cmd-S': save
    }
  });

  function loadFile(data) {
    filename.textContent = data.path;
    textarea.dataset.path = data.path;
    codeEditor.setOption('mode', modeFor(data.path));
    codeEditor.setValue(data.content);
    codeEditor.clearHistory();
  }

  function save() {
    const root = getRoot();
    const path = textarea.dataset.path;
    if (!root || !path) return;
    fetch('/api/file', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ root, path, content: codeEditor.getValue() })
    });
  }

  return { loadFile };
}

function modeFor(path) {
  const extension = path.split('.').pop().toLowerCase();
  return ({
    py: 'python', js: 'javascript', jsx: 'javascript', ts: 'javascript', tsx: 'javascript',
    c: 'text/x-csrc', h: 'text/x-csrc', cpp: 'text/x-c++src', hpp: 'text/x-c++src',
    java: 'text/x-java', html: 'xml', htm: 'xml', css: 'css', md: 'markdown'
  })[extension] || null;
}
