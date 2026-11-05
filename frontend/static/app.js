"use strict";

const $ = (id) => document.getElementById(id);
let buildings = [];
let viewedId = null;
let viewedRoom = null;
let buildingRooms = [];
let state = null;
let busy = false;
let polling = false;
let epoch = 0;

function setText(element, value) {
  // 定期照会で同じ内容を書き直さず、読み上げの繰り返しも防ぐ。
  if (element.textContent !== value) element.textContent = value;
}

function ledNote(building) {
  return building?.led_note || (building?.pin === null ? "画面案内のみ" : "");
}

function showMessage(id, message) {
  setText($(id), message || "");
  $(id).hidden = !message;
}

async function api(path, data) {
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), 9000);
  try {
    const response = await fetch(path, {
      method: data === undefined ? "GET" : "POST",
      headers: data === undefined ? {} : { "Content-Type": "application/json" },
      body: data === undefined ? undefined : JSON.stringify(data),
      signal: abort.signal,
      cache: "no-store",
    });
    const result = await response.json();
    if (!response.ok) {
      const error = new Error(result.error || "処理に失敗しました。");
      error.status = result.status;
      error.http = true;
      throw error;
    }
    return result;
  } catch (error) {
    if (error.http) throw error;
    throw new Error("サーバーとの通信を確認できません。起動用ターミナルを確認してください。LEDの状態は不明です。");
  } finally {
    clearTimeout(timer);
  }
}

function renderState() {
  if (!state) return;
  const simulation = state.mode === "simulation";
  const wiredCount = buildings.filter((item) => item.pin !== null).length;
  const on = state.led_state === "on";
  const badge = $("connection-badge");
  badge.className = `badge ${simulation ? "simulation" : state.connected ? "connected" : ""}`;
  setText(badge, simulation ? "シミュレーション" : state.connected ? "Arduino 接続中" : "Arduino 未接続");
  const banner = $("mode-banner");
  banner.className = `mode-banner ${simulation ? "simulation" : state.connected ? "connected" : ""}`;
  setText(banner, simulation
    ? "シミュレーションモード：画面上で点灯を確認できます。物理LEDへは送信しません。"
    : state.connected
      ? `実機モード：LED設定済みの${wiredCount}施設を案内します。4号館・レストラン棟はLED未実装です。`
      : "実機モード：Arduinoは未接続です。施設の閲覧はできます。実機がない場合は下の設定でシミュレーションに切り替えてください。");
  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.checked = radio.value === state.mode;
  });
  showMessage("notice", state.notice);
  const activeId = on ? state.active_building : null;
  document.querySelectorAll("[data-building]").forEach((button) => {
    const active = button.dataset.building === activeId;
    const viewed = button.dataset.building === viewedId;
    const note = ledNote(buildings.find((item) => item.id === button.dataset.building));
    button.classList.toggle("active", active);
    button.classList.toggle("viewed", viewed && !active);
    if (button.getAttribute("aria-pressed") !== String(viewed || active)) {
      button.setAttribute("aria-pressed", String(viewed || active));
    }
    const label = button.querySelector(".building-state");
    if (label) setText(label, active ? (simulation ? "模擬点灯" : "点灯中") : note || (viewed ? "選択中" : "↗"));
  });
  const building = buildings.find((item) => item.id === (viewedRoom ? viewedRoom.building_id : (viewedId || activeId)));
  setText($("destination-symbol"), building ? building.symbol : "↗");
  setText($("destination-name"), viewedRoom ? roomTitle(viewedRoom) : building ? building.name : "行き先を選んでください");
  setText($("destination-detail"), viewedRoom ? roomLocation(viewedRoom)
    : building ? `${building.name} · ${building.destination_count}地点。館内一覧から教室・施設を選べます。`
      : "一覧または地図の記号から選択できます。");
  document.querySelectorAll("[data-room]").forEach((button) => {
    const selected = button.dataset.room === viewedRoom?.id;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  const indicator = $("led-indicator");
  indicator.classList.toggle("on", on && building?.id === activeId);
  setText(indicator, viewedRoom && !building ? "棟名未記載" : building && (!building.simulation_led || (!simulation && building.pin === null)) ? "画面案内のみ"
    : state.led_state === "unknown" ? "LED状態不明"
    : on && building?.id === activeId ? (simulation ? "模擬点灯中" : "LED点灯中")
      : on ? "別の施設が点灯中" : "全消灯");
  const active = buildings.find((item) => item.id === activeId);
  setText($("led-summary"), state.led_state === "unknown"
    ? "物理LEDの状態は不明です。接続後に確認します。"
    : on ? `${active?.name || activeId} ${simulation ? "を画面上で点灯しています。" : "の点灯応答を確認しました。"}`
      : simulation ? "画面上のLEDはすべて消灯しています。" : `対応する${wiredCount}施設の全消灯応答を確認しました。`);
  setText($("port-detail"), state.connected ? `接続先：${state.port} / 9600bps` : "ポートを選んで再接続できます。互換機は手動で選択してください。");
  document.querySelectorAll("[data-control]").forEach((control) => { control.disabled = busy; });
  ["serial-port", "refresh-ports", "reconnect"].forEach((id) => { $(id).disabled = busy || simulation; });
}

function unknownState() {
  if (state) state = { ...state, connected: false, active_building: null, led_state: "unknown", notice: null };
}

async function action(work) {
  if (busy) return;
  busy = true;
  epoch += 1; // 処理前に始まった状態照会で、処理後の表示を上書きしない。
  document.querySelector("main").setAttribute("aria-busy", "true");
  showMessage("error", null);
  renderState();
  try {
    await work();
    if (state?.error) showMessage("error", state.error);
  } catch (error) {
    if (error.status) state = error.status;
    else if (!error.http) unknownState();
    showMessage("error", error.message);
  } finally {
    busy = false;
    document.querySelector("main").setAttribute("aria-busy", "false");
    renderState();
  }
}

function roomTitle(room) {
  return room.number && !room.name.includes(room.number) ? `${room.number} · ${room.name}` : room.name;
}

function roomLocation(room) {
  const building = buildings.find((item) => item.id === room.building_id);
  return [building?.name || "棟名未記載", room.floor || "階未記載", room.area, room.location_hint].filter(Boolean).join(" · ");
}

function showEvidence(room) {
  $("destination-evidence").hidden = !room;
  if (!room) return;
  setText($("location-note"), room.location_note || "LEDは建物の場所を示します。館内の位置は案内図で確認してください。");
  $("destination-plan").href = room.local_plan;
  $("destination-source").href = `${room.source}#page=${room.source_page}`;
  setText($("destination-verified"), `${room.source_label} ${room.source_page}ページ · 資料確認 ${room.verified_on}（現地未照合）`);
}

function renderRooms(container, rooms) {
  container.replaceChildren();
  rooms.forEach((room) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "room-button";
    button.dataset.room = room.id;
    button.dataset.control = "";
    const name = document.createElement("strong");
    name.textContent = roomTitle(room);
    const location = document.createElement("span");
    location.textContent = roomLocation(room);
    button.append(name, location);
    button.addEventListener("click", () => selectRoom(room));
    container.append(button);
  });
}

function renderBuildingRooms() {
  const floor = $("floor-filter").value;
  const rooms = buildingRooms.filter((room) => !floor || (room.floor || "未記載") === floor);
  renderRooms($("building-room-list"), rooms);
  setText($("building-room-count"), `${rooms.length} / ${buildingRooms.length}地点`);
  $("building-room-empty").hidden = rooms.length > 0;
  renderState();
}

async function loadBuildingRooms(id) {
  const building = buildings.find((item) => item.id === id);
  $("room-browser").hidden = !building;
  if (!building) { buildingRooms = []; return; }
  // 表示対象が変わるたびに、前の建物の階・部屋を消してから読み込む。
  $("building-room-list").replaceChildren();
  buildingRooms = [];
  setText($("room-browser-title"), `${building.name}の教室・施設`);
  $("building-plan").href = building.floorplan.local_url;
  setText($("building-room-count"), "読み込み中");
  $("building-room-empty").hidden = true;
  $("floor-filter").replaceChildren(new Option("すべての階", ""));
  buildingRooms = (await api(`/api/rooms?building_id=${encodeURIComponent(id)}`)).rooms;
  [...new Set(buildingRooms.map((room) => room.floor || "未記載"))].forEach((floor) => {
    $("floor-filter").add(new Option(floor, floor));
  });
  if (viewedRoom) $("floor-filter").value = viewedRoom.floor || "未記載";
  renderBuildingRooms();
}

async function guideBuilding(building) {
  if (!building || !building.simulation_led || (state?.mode === "real" && building.pin === null)) {
    // 案内できない建物へ移ったとき、前の行き先のLEDを残さない。
    if (state?.led_state === "on") state = (await api("/api/off", {})).status;
    showMessage("guide-note", building
      ? `${building.name}は${ledNote(building)}です。画面と案内図で場所を確認してください。`
      : "原図に棟名が明記されていないため、LED案内は行いません。該当ページを確認してください。");
    return;
  }
  showMessage("guide-note", building.led_note ? `${building.name}：${building.led_note}。` : null);
  state = (await api("/api/select", { building_id: building.id })).status;
}

function selectBuilding(id) {
  return action(async () => {
    viewedId = id;
    viewedRoom = null;
    showEvidence(null);
    renderState();
    await loadBuildingRooms(id);
    await guideBuilding(buildings.find((item) => item.id === id));
  });
}

function selectRoom(room) {
  return action(async () => {
    viewedRoom = room;
    viewedId = room.building_id;
    showEvidence(room);
    renderState();
    await loadBuildingRooms(room.building_id);
    await guideBuilding(buildings.find((item) => item.id === room.building_id));
  });
}

function renderList(items) {
  $("building-list").replaceChildren();
  $("result-count").textContent = `${items.length} / ${buildings.length}`;
  $("empty-results").hidden = items.length > 0;
  items.forEach((building) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "building-button";
    button.dataset.building = building.id;
    button.dataset.control = "";
    button.setAttribute("aria-label", `${building.name}を選択${building.pin === null ? `（${ledNote(building)}）` : "してLEDで案内"}`);
    const symbol = document.createElement("span");
    symbol.className = "building-symbol";
    symbol.textContent = building.symbol;
    const name = document.createElement("span");
    name.className = "building-name";
    name.textContent = building.name;
    const label = document.createElement("span");
    label.className = "building-state";
    label.textContent = "↗";
    button.append(symbol, name, label);
    button.addEventListener("click", () => selectBuilding(building.id));
    $("building-list").append(button);
  });
  renderState();
}

async function search(query) {
  const [result, rooms] = await Promise.all([
    api(`/api/buildings?q=${encodeURIComponent(query)}`),
    api(`/api/rooms?q=${encodeURIComponent(query)}`),
  ]);
  renderList(result.buildings);
  $("room-results").hidden = !query.trim() || !rooms.total;
  renderRooms($("search-room-list"), query.trim() ? rooms.rooms : []);
  $("empty-results").hidden = result.buildings.length > 0 || rooms.total > 0;
  $("search-message").textContent = result.message;
  renderState();
}

async function loadPorts() {
  const selected = $("serial-port").value;
  const result = await api("/api/ports");
  $("serial-port").replaceChildren(new Option("Unoを自動検出", ""));
  result.ports.forEach((port) => {
    $("serial-port").add(new Option(`${port.device} — ${port.description}`, port.device));
  });
  if (result.ports.some((port) => port.device === selected)) $("serial-port").value = selected;
}

async function loadMap() {
  const map = await api("/api/map");
  $("map-source").href = map.source_page;
  const wiredCount = buildings.filter((item) => item.pin !== null).length;
  setText($("map-count"), `地図${map.markers.length}施設 · 実機LED${wiredCount}施設 · 新・弓は略記`);
  const img = $("map-image");
  img.addEventListener("load", () => {
    img.hidden = false;
    $("map-loading").hidden = true;
    $("markers").hidden = false;
  });
  img.addEventListener("error", () => {
    $("markers").hidden = true;
    img.hidden = true;
    $("map-loading").hidden = false;
    $("map-loading").textContent = "地図画像を読み込めません。施設一覧から選択できます。";
  });
  $("markers").hidden = true;
  img.src = map.image;
  img.width = map.width;
  img.height = map.height;
  map.markers.forEach((marker) => {
    const building = buildings.find((item) => item.id === marker.id);
    if (!building) return;
    const button = document.createElement("button");
    button.className = "map-marker";
    button.type = "button";
    button.textContent = building.symbol;
    button.dataset.building = marker.id;
    button.dataset.control = "";
    button.style.left = `${marker.x}%`;
    button.style.top = `${marker.y}%`;
    button.title = building.name + (building.pin === null ? `（${ledNote(building)}）` : "");
    button.setAttribute("aria-label", `地図の${building.symbol} ${building.name}を選択${building.pin === null ? `（${ledNote(building)}）` : "してLEDで案内"}`);
    button.addEventListener("click", () => selectBuilding(marker.id));
    $("markers").append(button);
  });
}

$("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  action(() => search($("search").value));
});
$("reset-search").addEventListener("click", () => action(async () => {
  $("search").value = "";
  await search("");
}));
$("all-off").addEventListener("click", () => action(async () => {
  state = (await api("/api/off", {})).status;
  viewedId = null;
  viewedRoom = null;
  showEvidence(null);
  $("room-browser").hidden = true;
  showMessage("guide-note", null);
}));
document.querySelectorAll('input[name="mode"]').forEach((radio) => {
  radio.addEventListener("change", () => action(async () => {
    state = (await api("/api/mode", { mode: radio.value })).status;
    viewedId = null;
    viewedRoom = null;
    showEvidence(null);
    $("room-browser").hidden = true;
    showMessage("guide-note", null);
    if (state.mode === "real") await loadPorts();
  }));
});
$("floor-filter").addEventListener("change", renderBuildingRooms);
$("refresh-ports").addEventListener("click", () => action(loadPorts));
$("reconnect").addEventListener("click", () => action(async () => {
  const port = $("serial-port").value;
  state = (await api("/api/connection", port ? { port } : {})).status;
}));

async function poll() {
  if (busy || polling || !state) return;
  const started = epoch;
  polling = true;
  try {
    const result = await api("/api/status");
    if (started !== epoch) return;
    state = result.status;
    renderState();
    showMessage("error", state.error);
  } catch (error) {
    if (started !== epoch) return;
    unknownState();
    renderState();
    showMessage("error", error.message);
  } finally {
    polling = false;
  }
}

async function initialize() {
  await action(async () => {
    const result = await api("/api/buildings");
    buildings = result.buildings;
    state = (await api("/api/status")).status;
    renderList(buildings);
    $("search-message").textContent = result.message;
    $("data-note").textContent = `公式案内図${result.source_count}点から、番号付きの室${result.verified_room_count}件・全${result.destination_count}地点を登録。棟や階の未記載箇所は明示します。図面との照合済み・現地未照合です。`;
    // 片方が失敗しても施設選択は使えるようにする。
    const results = await Promise.allSettled([loadMap(), loadPorts()]);
    const failed = results.find((item) => item.status === "rejected");
    if (failed) throw failed.reason;
  });
  if (!state) $("search-message").textContent = "読み込みに失敗しました。サーバーを確認してページを再読み込みしてください。";
  setInterval(poll, 2000);
}

initialize();
