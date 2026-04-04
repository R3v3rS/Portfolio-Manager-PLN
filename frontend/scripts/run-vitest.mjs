import { spawn } from 'node:child_process';

const forwardedArgs = process.argv.slice(2).filter((arg) => arg !== '--runInBand');
const vitestArgs = ['run', ...forwardedArgs];

const child = spawn('npx', ['vitest', ...vitestArgs], { stdio: 'inherit', shell: process.platform === 'win32' });

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
