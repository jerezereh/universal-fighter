// Authored COM failures exercise ownership cleanup without loading a game or Frida.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function fixture(failure = null, drift = false) {
    const calls = [];
    const nullPointer = {isNull: () => true};
    function allocation() {
        return {pointer: nullPointer, values: new Map(), readPointer() {return this.pointer;},
            writePointer(p) {this.pointer = p;}, readU32() {return this.values.get(0);},
            readS32() {return this.values.get(0);}, add(offset) {
                return {readU32: () => this.values.get(offset), readPointer: () => this.pointer};
            }};
    }
    const source = {isNull: () => false, toString: () => '0x10000'}, destination = {isNull: () => false};
    const pixels = {isNull: () => false, add: offset => ({offset})};
    const root = {add: () => ({readU32: () => drift ? 10 : 9})};
    const module = {base: {add: () => ({readPointer: () => ({equals: p => p === root})})}};
    const context = vm.createContext({rpc: {exports: {}}, Memory: {alloc: allocation},
        ptr: () => nullPointer, Uint8Array, Map, DataView, Process: {mainModule: module}});
    vm.runInContext(fs.readFileSync(__dirname + '/xrd-sign-boundary.js', 'utf8'), context);
    context.fixtureCom = (object, slot) => (...args) => {
        const method = object === source || object === destination ?
            ({2: 'Release', 12: 'GetDesc', 13: 'LockRect', 14: 'UnlockRect'})[slot] :
            ({18: 'GetBackBuffer', 38: 'GetRenderTarget', 36: 'CreateOffscreenPlainSurface', 32: 'GetRenderTargetData'})[slot];
        calls.push([method, object]);
        if (failure === method) return -1;
        if (method === 'GetBackBuffer') args[4].pointer = source;
        if (method === 'GetRenderTarget') args[2].pointer = source;
        if (method === 'GetDesc') {
            for (const [offset, value] of [[0, 21], [16, 0], [24, 2], [28, 2]]) args[1].values.set(offset, value);
        }
        if (method === 'CreateOffscreenPlainSurface') args[5].pointer = destination;
        if (method === 'LockRect') {args[1].values.set(0, 16); args[1].pointer = pixels;}
        return 0;
    };
    context.fixtureSnapshot = () => ({segments: [], data: Uint8Array.from([1, 2, 3, 4]).buffer});
    context.fixtureBytes = address => {
        assert.ok([0, 16].includes(address.offset), 'row copy ignored source pitch');
        return Uint8Array.from(address.offset === 0 ? [5, 6, 7, 8, 9, 10, 11, 12] : [13, 14, 15, 16, 17, 18, 19, 20]);
    };
    context.device = {toString: () => 'authored-device'};
    context.root = root;
    vm.runInContext('com = fixtureCom; snapshot = fixtureSnapshot; bytes = fixtureBytes;' +
        'config = {state: {engine_global_rva: 0}, candidate: {counter_field: 0}};' +
        'gate = {resumed: false, executing: false}; renderCapture.presentations = 3;', context);
    return {calls, source, destination, run: () => vm.runInContext('captureBackBuffer(device, root, 9)', context),
        intermediate: () => vm.runInContext('captureBackBuffer(device, root, 9, true)', context)};
}

const normal = fixture();
const captured = normal.run();
assert.deepEqual([...new Uint8Array(captured.data)], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]);
assert.equal(captured.metadata.isolated_rgba, false);
assert.equal(normal.calls.filter(([name]) => name === 'UnlockRect').length, 1);
assert.deepEqual(normal.calls.filter(([name]) => name === 'Release').map(([, object]) => object),
    [normal.destination, normal.source]);
for (const failure of ['GetBackBuffer', 'GetDesc', 'CreateOffscreenPlainSurface', 'GetRenderTargetData', 'LockRect', 'UnlockRect']) {
    const f = fixture(failure);
    assert.throws(f.run, new RegExp(failure + ' failed'));
    const released = f.calls.filter(([name]) => name === 'Release').map(([, object]) => object);
    assert.deepEqual(released, failure === 'GetBackBuffer' ? [] :
        ['GetDesc', 'CreateOffscreenPlainSurface'].includes(failure) ? [f.source] : [f.destination, f.source]);
    assert.equal(f.calls.filter(([name]) => name === 'UnlockRect').length, failure === 'UnlockRect' ? 1 : 0);
}
const drift = fixture(null, true);
assert.throws(drift.run, /source advanced during readback/);
assert.equal(drift.calls.filter(([name]) => name === 'Release').length, 2);
assert.equal(drift.calls.filter(([name]) => name === 'UnlockRect').length, 1);
const target = fixture();
const pass = target.intermediate();
assert.equal(pass.metadata.kind, 'render-pass');
assert.equal(pass.metadata.surface, '0x10000');
assert.equal(pass.metadata.pixel_bytes, 4);
assert.equal(pass.metadata.presentation_index, null);
assert.equal(target.calls.filter(([name]) => name === 'Release').length, 2);
const missing = fixture('GetRenderTarget');
assert.throws(missing.intermediate, /GetRenderTarget failed/);
assert.equal(missing.calls.filter(([name]) => name === 'Release').length, 0);
console.log('Authored COM readback failure, source drift, unlock and independent release checks passed.');
