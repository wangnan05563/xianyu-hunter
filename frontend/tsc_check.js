const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const cwd = 'd:/code/otherProjects/17_xianyu/frontend';
const tscPath = path.join(cwd, 'node_modules/typescript/lib/tsc.js');

console.log('Starting tsc check...');
console.log('tsc path:', tscPath);
console.log('cwd:', cwd);

const r = spawnSync(process.execPath, [tscPath, '--noEmit', '--pretty', 'false'], {
  encoding: 'utf8',
  cwd: cwd,
  timeout: 600000,
});

const out = `STDOUT_LEN: ${(r.stdout || '').length}\nSTDERR_LEN: ${(r.stderr || '').length}\nEXIT_CODE: ${r.status}\nERROR: ${r.error ? r.error.message : 'none'}\nSIGNAL: ${r.signal || 'none'}\n\nSTDOUT_FIRST_500:\n${(r.stdout || '').slice(0, 500)}\n\nSTDERR_FIRST_500:\n${(r.stderr || '').slice(0, 500)}\n`;

console.log(out);
fs.writeFileSync(path.join(cwd, 'tsc_output.txt'), out, 'utf8');
