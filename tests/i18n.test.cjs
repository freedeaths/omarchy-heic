const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, 'plugin/I18n.js'), 'utf8').replace(/^\.pragma library\s*/, ''), context);
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'plugin/i18n.json'), 'utf8'));
assert.equal(context.language('zh_CN.UTF-8', 'en_US', 'en_US', ''), 'zh_CN');
assert.equal(context.language('C.UTF-8', 'zh_CN', 'zh_CN', ''), 'en');
assert.equal(context.language('', 'zh_CN.UTF-8', 'en_US', ''), 'zh_CN');
assert.equal(context.language('', '', '', 'zh_CN'), 'zh_CN');
for (const [locale, expected] of Object.entries({ja_JP:'ja',ko_KR:'ko',es_ES:'es',fr_FR:'fr',de_DE:'de',pt_BR:'pt',pt_PT:'pt',ru_RU:'ru'})) {
  assert.equal(context.language('', '', locale + '.UTF-8', ''), expected);
  assert.equal(context.text(catalog, expected, 'preview'), catalog[expected].preview);
}
assert.equal(context.language('', '', 'it_IT.UTF-8', ''), 'en');
const keys = Object.keys(catalog.en).sort();
for (const [locale, values] of Object.entries(catalog)) {
  assert.deepEqual(Object.keys(values).sort(), keys, locale);
  for (const key of keys) {
    assert.deepEqual((values[key].match(/\{\w+\}/g) || []).sort(), (catalog.en[key].match(/\{\w+\}/g) || []).sort(), locale + ':' + key);
  }
}
assert.equal(context.text(catalog, 'zh_CN', 'frame', { index: 2, count: 8 }), '第 2 / 8 帧');
assert.equal(context.text(catalog, 'unknown', 'preview_day'), 'Preview a day');
assert.equal(context.message(catalog, 'zh_CN', 'External wallpaper selected'), '已选择其他壁纸，自动暂停');
assert.equal(context.message(catalog, 'zh_CN', 'unknown backend detail'), 'unknown backend detail');
console.log('i18n locale precedence, fallback, interpolation and message translation passed');
