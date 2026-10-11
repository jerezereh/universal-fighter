// One Escape sequence on the source polling thread; no focus or global input.
let hook, target, original, config, phase = 0;
const events = [];
const bytes = p => Array.from(new Uint8Array(p.readByteArray(32)));
rpc.exports = {
  start(c) {
    if (hook || c.pid !== Process.id || c.module_base !== Process.mainModule.base.toUInt32())
      throw Error('source session changed');
    config = c;
    const user = Process.getModuleByName('user32.dll');
    const getWindow = new NativeFunction(user.getExportByName('GetWindowLongW'), 'pointer', ['pointer', 'int'], 'stdcall');
    const owner = new NativeFunction(user.getExportByName('GetWindowThreadProcessId'), 'uint', ['pointer', 'pointer'], 'stdcall');
    const ownerOut = Memory.alloc(4);
    const foreground = new NativeFunction(user.getExportByName('GetForegroundWindow'), 'pointer', [], 'stdcall');
    config.foreground_before = foreground().toString();
    target = user.getExportByName('GetKeyState'); original = bytes(target);
    hook = Interceptor.attach(target, {
      onEnter(args) {
        this.active = args[0].toInt32() === 27 &&
          this.returnAddress.equals(Process.mainModule.base.add(config.poll_return_rva));
        if (this.active) this.viewport = this.context.ebx;
      },
      onLeave(value) {
        if (!this.active || phase >= 10) return;
        const hwnd = this.viewport.add(config.hwnd_offset).readPointer();
        owner(hwnd, ownerOut);
        const fn = getWindow(hwnd, -4);
        if (ownerOut.readU32() !== Process.id || !fn.equals(Process.mainModule.base.add(config.window_handler_rva)))
          throw Error('source window handler changed');
        const step = phase++;
        value.replace(step < 8 ? 65408 : 1);
        if (step !== 0 && step !== 8) return;
        const call = new NativeFunction(fn, 'int', ['pointer', 'uint', 'uint', 'int'], 'stdcall');
        const result = call(hwnd, step === 0 ? 0x100 : 0x101, 27, step === 0 ? 0x10001 : -1073676287);
        events.push({step, result, thread: Process.getCurrentThreadId()});
      }
    });
  },
  status() { return {phase, events}; },
  stop() {
    if (hook) { hook.detach(); hook = null; Interceptor.flush(); }
    const foreground = new NativeFunction(Process.getModuleByName('user32.dll').getExportByName('GetForegroundWindow'), 'pointer', [], 'stdcall');
    return {phase, events, code_restored: JSON.stringify(bytes(target)) === JSON.stringify(original),
      foreground_unchanged: foreground().toString() === config.foreground_before};
  }
};
