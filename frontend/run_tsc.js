// 简单调试：运行 tsc 并把结果写入文件
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const tsc = spawnSync(
  'node',
  [path.join(__dirname, 'node_modules', 'typescript', 'bin', 'tsc'), '--noEmit', '--pretty', 'false'],
  { encoding: 'utf8', cwd: __dirname, timeout: 120000 }
);
const out = `STDOUT:\n${tsc.stdout}\nSTDERR:\n${tsc.stderr}\nEXITCODE: ${tsc.status}\nERROR: ${tsc.error ? tsc.error.message : 'none'}\n`;
fs.writeFileSync(path.join(__dirname, 'tsc_result.log'), out, 'utf8');
console.log('DONE', tsc.status);
