import assert from 'node:assert/strict';

import { imageSize } from '../third_party/image-size/dist/index.mjs';
import { HEIF } from '../third_party/image-size/dist/types/heif.mjs';
import { JXL } from '../third_party/image-size/dist/types/jxl.mjs';

const icns = Buffer.alloc(16);
icns.write('icns', 0, 'ascii');
icns.writeUInt32BE(16, 4);
icns.write('ic07', 8, 'ascii');
icns.writeUInt32BE(0, 12);

assert.throws(
  () => imageSize(icns),
  /image entry length is out of bounds/,
  'ICNS entries with a zero length must be rejected before the parser loops.',
);

const jxl = Buffer.alloc(16);
jxl.write('JXL ', 4, 'ascii');
assert.equal(JXL.validate(jxl), false, 'JXL boxes with a zero length must be rejected.');

const heif = Buffer.alloc(16);
heif.write('ftyp', 4, 'ascii');
heif.write('heic', 8, 'ascii');
assert.equal(HEIF.validate(heif), false, 'HEIF boxes with a zero length must be rejected.');

console.log('Vendored image-size parser guards passed.');
