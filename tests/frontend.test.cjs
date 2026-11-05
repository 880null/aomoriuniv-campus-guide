// DOMと実際のFlask APIを接続して検査する。実ブラウザ・USBの検証ではない。
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {createInterface} = require('node:readline');
const {readFileSync} = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '..');
const python = process.env.CAMPUS_TEST_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

async function waitFor(check) {
  const deadline = Date.now() + 5000;
  while (!check()) {
    if (Date.now() > deadline) throw new Error('DOMの更新が完了しませんでした');
    await new Promise(resolve => setTimeout(resolve, 10));
  }
}

async function setup(t) {
  const bridge = spawn(python, ['-u', '-c', `
import json, sys
from backend.app import create_app
from backend.controller import LedController
app = create_app(LedController('simulation', ports_provider=lambda: []))
client = app.test_client()
for line in sys.stdin:
    request = json.loads(line)
    response = client.open(request['path'], method=request['method'], json=request.get('body'))
    print(json.dumps({'id':request['id'], 'ok':response.status_code < 400, 'body':response.get_json()}), flush=True)
`], {cwd:root, stdio:['pipe','pipe','pipe']});
  const pending = new Map();
  let sequence = 0;
  const requests = [];
  createInterface({input:bridge.stdout}).on('line', line => {
    const value = JSON.parse(line);
    pending.get(value.id)?.resolve(value);
    pending.delete(value.id);
  });
  let stderr = '';
  bridge.stderr.on('data', chunk => { stderr += chunk; });
  const failPending = error => {
    for (const task of pending.values()) task.reject(error);
    pending.clear();
  };
  bridge.on('error', failPending);
  bridge.on('exit', code => failPending(new Error(`Flask検証プロセスが終了しました (${code}): ${stderr}`)));
  const dom = new JSDOM(readFileSync(path.join(root,'frontend/index.html'),'utf8'), {
    url:'http://localhost/', runScripts:'outside-only',
  });
  t.after(() => { dom.window.close(); bridge.stdin.end(); bridge.kill(); });
  const {window} = dom;
  window.setInterval = () => 1;
  window.fetch = async (requestPath, options) => {
    const request = {id:++sequence, path:requestPath, method:options.method};
    if (options.body) request.body = JSON.parse(options.body);
    requests.push(request);
    const response = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(request.id);
        reject(new Error(`Flask検証APIが応答しません: ${requestPath}`));
      }, 8000);
      pending.set(request.id, {
        resolve: value => { clearTimeout(timer); resolve(value); },
        reject: error => { clearTimeout(timer); reject(error); },
      });
      bridge.stdin.write(JSON.stringify(request)+'\n', error => {
        if (error) pending.get(request.id)?.reject(error);
      });
    });
    return {ok:response.ok, json:async () => response.body};
  };
  window.eval(readFileSync(path.join(root,'frontend/static/app.js'),'utf8'));
  const $ = id => window.document.getElementById(id);
  await waitFor(() => $('connection-badge').textContent === 'シミュレーション' && $('markers').children.length === 13);
  await waitFor(() => window.document.querySelector('main').getAttribute('aria-busy') === 'false');
  assert.equal(stderr,'');
  const idle = () => waitFor(() => window.document.querySelector('main').getAttribute('aria-busy') === 'false');
  const search = async query => {
    $('search').value = query;
    $('search-form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
    await idle();
  };
  const clickBuilding = async id => {
    window.document.querySelector(`.map-marker[data-building="${id}"]`).click();
    await idle();
  };
  return {window, $, requests, idle, search, clickBuilding};
}

test('番号検索・階・出典と、LEDなし施設選択時の消灯', async t => {
  const ui = await setup(t);
  assert.equal(ui.$('building-list').children.length,14);
  await ui.search('５３０１教室');
  assert.equal(ui.$('search-room-list').children.length,1);
  ui.$('search-room-list').firstElementChild.click();
  await ui.idle();
  assert.match(ui.$('destination-name').textContent,/5301.*コンピュータ演習室A/);
  assert.match(ui.$('destination-detail').textContent,/5号館.*3階/);
  assert.match(ui.$('destination-plan').href,/D.pdf#page=2$/);
  assert.equal(ui.$('led-indicator').textContent,'模擬点灯中');
  await ui.clickBuilding('G');
  assert.equal(ui.$('led-indicator').textContent,'画面案内のみ');
  assert.equal(ui.requests.filter(r=>r.method==='POST').at(-1).path,'/api/off');
  assert.match(ui.$('led-summary').textContent,/すべて消灯/);
  ui.$('floor-filter').value='2階';
  ui.$('floor-filter').dispatchEvent(new ui.window.Event('change'));
  assert.equal(ui.$('building-room-list').children.length,2);
});

test('同名室は別候補、棟不明地点は原図へ案内してLEDを消灯', async t => {
  const ui = await setup(t);
  await ui.clickBuilding('B');
  ui.$('floor-filter').value='1階';
  ui.$('floor-filter').dispatchEvent(new ui.window.Event('change'));
  const laboratories = [...ui.$('building-room-list').children].filter(b=>b.querySelector('strong').textContent==='実習室');
  assert.equal(laboratories.length,4);
  assert.equal(new Set(laboratories.map(b=>b.textContent)).size,4);
  await ui.search('書庫');
  const unknown = [...ui.$('search-room-list').children].find(b=>b.textContent.includes('棟名未記載'));
  assert.ok(unknown);
  unknown.click();
  await ui.idle();
  assert.equal(ui.$('led-indicator').textContent,'棟名未記載');
  assert.match(ui.$('destination-detail').textContent,/階未記載/);
  assert.match(ui.$('destination-plan').href,/A.pdf#page=1$/);
  assert.equal(ui.requests.filter(r=>r.method==='POST').at(-1).path,'/api/off');
});

test('実機未接続でも教室情報を維持し、点灯成功と表示しない', async t => {
  const ui = await setup(t);
  const radio=ui.window.document.querySelector('input[value="real"]');
  radio.checked=true;
  radio.dispatchEvent(new ui.window.Event('change'));
  await ui.idle();
  await ui.search('保健室');
  ui.$('search-room-list').firstElementChild.click();
  await ui.idle();
  assert.match(ui.$('destination-detail').textContent,/7号館.*1階/);
  assert.equal(ui.$('destination-name').textContent,'711 · 保健室');
  assert.equal(ui.$('connection-badge').textContent,'Arduino 未接続');
  assert.equal(ui.$('led-indicator').textContent,'LED状態不明');
  assert.equal(ui.$('destination-evidence').hidden,false);
  for (const key of ['C', 'H']) {
    await ui.clickBuilding(key);
    assert.equal(ui.$('led-indicator').textContent,'画面案内のみ');
    assert.equal(ui.requests.some(r=>r.path==='/api/select' && r.body.building_id===key),false);
  }
});
