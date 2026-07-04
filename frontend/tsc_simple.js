// 极简 tsc 检查 - 只写文件
const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const cwd = 'd:/code/otherProjects/17_xianyu/frontend';
const tscPath = path.join(cwd, 'node_modules/typescript/lib/tsc.js');

const r = spawnSync(process.execPath, [tscPath, '--noEmit', '--pretty', 'false'], {
  encoding: 'utf8',
  cwd: cwd,
  timeout: 600000,
});

const out = JSON.stringify({
  exit: r.status,
  signal: r.signal,
  error: r.error ? r.error.message : null,
  stdout_len: (r.stdout || '').length,
  stderr_len: (r.stderr || '').length,
  stdout: r.stdout || '',
  stderr: r.stderr || '',
}, null, 2);

fs.writeFileSync(path.join(cwd, 'tsc_simple_result.json'), out, 'utf8');
