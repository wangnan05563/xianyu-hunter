// 运行 tsc 并把结果写入文件
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

try {
  const tsc = spawnSync(
    'node',
    [path.join('node_modules', 'typescript', 'lib', 'tsc.js'), '--noEmit', '--pretty', 'false'],
    { encoding: 'utf8', cwd: __dirname, timeout: 300000 }
  );
  const out = `STDOUT: ${tsc.stdout}\nSTDERR: ${tsc.stderr}\nEXITCODE: ${tsc.status}\nERROR: ${tsc.error ? tsc.error.message : 'none'}\n`;
  fs.writeFileSync(path.join(__dirname, 'tsc_run.log'), out, 'utf8');
  process.exit(0);
} catch (e) {
  fs.writeFileSync(path.join(__dirname, 'tsc_run.log'), 'EXCEPTION: ' + e.message, 'utf8');
  process.exit(1);
}
