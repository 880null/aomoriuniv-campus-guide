"use strict";

const $ = (id) => document.getElementById(id);
let buildings = [];
let viewedId = null;
let state = null;
let busy = false;
let polling = false;
let epoch = 0;

function setText(element, value) {
  // 定期照会で同じ内容を書き直さず、読み上げの繰り返しも防ぐ。
  if (element.textContent !== value) element.textContent = value;
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
  const on = state.led_state === "on";
  const badge = $("connection-badge");
  badge.className = `badge ${simulation ? "simulation" : state.connected ? "connected" : ""}`;
  setText(badge, simulation ? "シミュレーション" : state.connected ? "Arduino 接続中" : "Arduino 未接続");
  const banner = $("mode-banner");
  banner.className = `mode-banner ${simulation ? "simulation" : state.connected ? "connected" : ""}`;
  setText(banner, simulation
    ? "シミュレーションモード：画面上で点灯を確認できます。物理LEDへは送信しません。"
    : state.connected
      ? "実機モード：配線確認済みの5施設をLEDで案内します。4号館・レストラン棟の配線は未確認です。"
      : "実機モード：Arduinoは未接続です。施設の閲覧はできます。実機がない場合は下の設定でシミュレーションに切り替えてください。");
  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.checked = radio.value === state.mode;
  });
  showMessage("notice", state.notice);
  const activeId = on ? state.active_building : null;
  document.querySelectorAll("[data-building]").forEach((button) => {
    const active = button.dataset.building === activeId;
    const viewed = button.dataset.building === viewedId;
    const unwired = buildings.find((item) => item.id === button.dataset.building)?.pin === null;
    button.classList.toggle("active", active);
    button.classList.toggle("viewed", viewed && !active);
    if (button.getAttribute("aria-pressed") !== String(viewed || active)) {
      button.setAttribute("aria-pressed", String(viewed || active));
    }
    const label = button.querySelector(".building-state");
    if (label) setText(label, active ? (simulation ? "模擬点灯" : "点灯中") : unwired ? "配線未確認" : viewed ? "選択中" : "↗");
  });
  const building = buildings.find((item) => item.id === (viewedId || activeId));
  setText($("destination-symbol"), building ? building.id : "↗");
  setText($("destination-name"), building ? building.name : "行き先を選んでください");
  setText($("destination-detail"), building
    ? `地図記号 ${building.id} · ${building.name}　${building.pin === null ? "配線未確認のため、実機LEDの点灯は保留しています。" : "教室の詳細配置は確認中です。"}`
    : "一覧または地図の記号から選択できます。");
  const indicator = $("led-indicator");
  indicator.classList.toggle("on", on && building?.id === activeId);
  setText(indicator, !simulation && building?.pin === null ? "配線未確認"
    : state.led_state === "unknown" ? "LED状態不明"
    : on && building?.id === activeId ? (simulation ? "模擬点灯中" : "LED点灯中")
      : on ? "別の施設が点灯中" : "全消灯");
  const active = buildings.find((item) => item.id === activeId);
  setText($("led-summary"), state.led_state === "unknown"
    ? "物理LEDの状態は不明です。接続後に確認します。"
    : on ? `${active?.name || activeId} ${simulation ? "を画面上で点灯しています。" : "の点灯応答を確認しました。"}`
      : simulation ? "画面上のLEDはすべて消灯しています。" : "対応する5施設の全消灯応答を確認しました。");
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

function selectBuilding(id) {
  if (busy) return;
  viewedId = id;
  renderState();
  const building = buildings.find((item) => item.id === id);
  if (state?.mode === "real" && building?.pin === null) {
    showMessage("error", `${building.name}は配線未確認です。施設情報のみ表示し、点灯命令は送信しません。`);
    return;
  }
  return action(async () => { state = (await api("/api/select", { building_id: id })).status; });
}

function renderList(items) {
  $("building-list").replaceChildren();
  $("result-count").textContent = `${items.length} / 7`;
  $("empty-results").hidden = items.length > 0;
  items.forEach((building) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "building-button";
    button.dataset.building = building.id;
    button.dataset.control = "";
    button.setAttribute("aria-label", `${building.id} ${building.name}を選択${building.pin === null ? "（実機の配線は未確認）" : "してLEDで案内"}`);
    const symbol = document.createElement("span");
    symbol.className = "building-symbol";
    symbol.textContent = building.id;
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
  const result = await api(`/api/buildings?q=${encodeURIComponent(query)}`);
  renderList(result.buildings);
  $("search-message").textContent = result.message;
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
    button.textContent = marker.id;
    button.dataset.building = marker.id;
    button.dataset.control = "";
    button.style.left = `${marker.x}%`;
    button.style.top = `${marker.y}%`;
    button.title = building.name + (building.pin === null ? "（配線未確認）" : "");
    button.setAttribute("aria-label", `地図の${marker.id} ${building.name}を選択${building.pin === null ? "（実機の配線は未確認）" : "してLEDで案内"}`);
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
}));
document.querySelectorAll('input[name="mode"]').forEach((radio) => {
  radio.addEventListener("change", () => action(async () => {
    state = (await api("/api/mode", { mode: radio.value })).status;
    viewedId = null;
    if (state.mode === "real") await loadPorts();
  }));
});
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
    $("data-note").textContent = `確認済み教室：${result.verified_room_count}件。未登録の教室は推測で案内しません。施設名または地図からお探しください。`;
    // 片方が失敗しても施設選択は使えるようにする。
    const results = await Promise.allSettled([loadMap(), loadPorts()]);
    const failed = results.find((item) => item.status === "rejected");
    if (failed) throw failed.reason;
  });
  if (!state) $("search-message").textContent = "読み込みに失敗しました。サーバーを確認してページを再読み込みしてください。";
  setInterval(poll, 2000);
}

initialize();
