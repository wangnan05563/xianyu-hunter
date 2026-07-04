const path = require('path');
const fs = require('fs');
const { spawnSync } = require('child_process');

const cwd = 'd:/code/otherProjects/17_xianyu/frontend';
const vitestPath = path.join(cwd, 'node_modules/vitest/vitest.mjs');

const r = spawnSync(process.execPath, [vitestPath, 'run', 'src/pages/Evaluations/__tests__/resolveActionDisplay.test.ts', '--reporter=verbose'], {
  encoding: 'utf8',
  cwd: cwd,
  timeout: 300000,
});

const out = `STDOUT:\n${r.stdout || '(empty)'}\n\nSTDERR:\n${r.stderr || '(empty)'}\n\nEXIT_CODE: ${r.status}\n\nERROR: ${r.error ? r.error.message : 'none'}\n\nSIGNAL: ${r.signal || 'none'}\n`;
const outPath = path.join(cwd, 'vitest_result.log');
fs.writeFileSync(outPath, out, 'utf8');
process.stdout.write(out);
