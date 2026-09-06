// Translate legacy keyboard scenarios into the equivalent line commands.
// Dedicated plain-mode tests use literal command lines instead.
export function commandLines(keys) {
  const names = { '\x1b[A': 'up', '\x1b[B': 'down', '\x1b': 'esc', '\x03': '\x03', '\r': 'enter', '\n': 'enter', ' ': 'space', '\t': 'tab', '\x7f': 'backspace' };
  return (keys.match(/\x1b\[[AB]|[\s\S]/g) || []).map((key) => names[key] || key).join('\n') + '\n';
}
