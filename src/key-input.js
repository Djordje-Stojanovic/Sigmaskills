import readline from 'node:readline';
import { PassThrough } from 'node:stream';

export class KeyInput {
  constructor(stdin, lineMode = false) {
    this.stdin = stdin;
    this.queue = [];
    this.waiters = [];
    this.ended = false;
    this.closed = false;
    this.previousRawMode = Boolean(stdin.isRaw);
    this.previousFlowing = stdin.readableFlowing;
    this.changedRawMode = false;

    this.lineMode = lineMode;
    this.onKeypress = (_value, key = {}) => {
      const normalized = key.ctrl && key.name === 'c'
        ? { name: 'ctrl-c', ch: '', sequence: '', shift: false }
        : {
          name: key.name || key.sequence || 'unknown',
          ch: typeof _value === 'string' ? _value : '',
          sequence: key.sequence || '',
          shift: Boolean(key.shift),
        };
      this.push(normalized);
    };
    this.onEnd = () => {
      this.ended = true;
      this.push({ name: 'eof' });
    };
    this.onSigint = () => this.push({ name: 'ctrl-c' });
    this.onError = (error) => this.push({ name: 'input-error', error });

    if (lineMode) {
      this.lines = readline.createInterface({ input: stdin, terminal: false, crlfDelay: Infinity });
      this.lines.on('line', (line) => {
        const command = line.trim();
        const aliases = { enter: 'return', esc: 'escape', cancel: 'escape' };
        this.push({ name: aliases[command] || command || 'return', ch: command, line: true });
      });
      this.lines.once('close', this.onEnd);
      // Ctrl+C must work in a pipe as well as in a cooked terminal.
      this.onControl = (chunk) => {
        if (chunk.includes('\x03')) this.onSigint();
      };
      stdin.on('data', this.onControl);
    } else {
      // Give readline a private stream so its parser listeners cannot leak onto stdin.
      this.parser = new PassThrough();
      readline.emitKeypressEvents(this.parser);
      this.parser.on('keypress', this.onKeypress);
      stdin.pipe(this.parser);
    }
    stdin.once('end', this.onEnd);
    stdin.on('error', this.onError);
    process.on('SIGINT', this.onSigint);

    if (!lineMode && stdin.isTTY && typeof stdin.setRawMode === 'function') {
      stdin.setRawMode(true);
      this.changedRawMode = true;
    }
    stdin.resume?.();
  }

  push(key) {
    const waiter = this.waiters.shift();
    if (waiter) {
      clearTimeout(waiter.timer);
      waiter.resolve(key);
    } else {
      this.queue.push(key);
    }
  }

  next(timeoutMs) {
    if (this.queue.length > 0) return Promise.resolve(this.queue.shift());
    if (this.ended) return Promise.resolve({ name: 'eof' });

    return new Promise((resolve) => {
      const waiter = { resolve, timer: null };
      if (timeoutMs !== undefined) {
        waiter.timer = setTimeout(() => {
          const index = this.waiters.indexOf(waiter);
          if (index !== -1) this.waiters.splice(index, 1);
          resolve(null);
        }, timeoutMs);
      }
      this.waiters.push(waiter);
    });
  }

  close() {
    if (this.closed) return;
    this.closed = true;
    if (this.lines) {
      this.lines.removeListener('close', this.onEnd);
      this.lines.close();
      this.stdin.removeListener('data', this.onControl);
    }
    if (this.parser) {
      this.stdin.unpipe(this.parser);
      this.parser.removeAllListeners();
      this.parser.destroy();
    }
    this.stdin.removeListener('end', this.onEnd);
    this.stdin.removeListener('error', this.onError);
    process.removeListener('SIGINT', this.onSigint);
    for (const waiter of this.waiters.splice(0)) {
      clearTimeout(waiter.timer);
      waiter.resolve({ name: 'eof' });
    }
    if (this.changedRawMode) {
      try {
        this.stdin.setRawMode(this.previousRawMode);
      } catch {
        // The stream may already be closed. Cursor restoration still runs.
      }
    }
    if (this.previousFlowing !== true && typeof this.stdin.pause === 'function') {
      this.stdin.pause();
    }
  }
}
