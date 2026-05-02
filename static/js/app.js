/* FuzzyRide — frontend logic for 10 fuzzy variables / 3 FIS */

const SLIDERS = [
  { id: 'distance',            fmt: v => `${v.toFixed(1)} km` },
  { id: 'estimated_time',      fmt: v => `${v.toFixed(0)} phút` },
  { id: 'time_of_day',         fmt: v => {
      const h = Math.floor(v), m = Math.round((v - h) * 60);
      return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
    }},
  { id: 'traffic_level',       fmt: v => v.toFixed(1) },
  { id: 'weather',             fmt: v => v.toFixed(2) },
  { id: 'temperature',         fmt: v => `${v.toFixed(1)}°C` },
  { id: 'air_quality',         fmt: v => `${v.toFixed(0)}` },
  { id: 'demand_level',        fmt: v => v.toFixed(1) },
  { id: 'driver_availability', fmt: v => `${v.toFixed(0)} xe` },
];

const ALL_INPUT_VARS = SLIDERS.map(s => s.id).concat(['day_type']);
const ALL_VARS = ALL_INPUT_VARS.concat(['base_multiplier', 'environment_factor', 'surge_factor']);

const VAR_LABELS = {
  distance: 'Quãng đường', estimated_time: 'Thời gian dự kiến',
  time_of_day: 'Giờ trong ngày', day_type: 'Loại ngày',
  traffic_level: 'Mức kẹt xe', weather: 'Thời tiết',
  temperature: 'Nhiệt độ', air_quality: 'Chất lượng KK',
  demand_level: 'Mức cầu', driver_availability: 'Tài xế khả dụng',
  base_multiplier: 'Base Multiplier (FIS-1)',
  environment_factor: 'Environment Factor (FIS-2)',
  surge_factor: 'Surge Factor (FIS-3)',
};

const TERM_VI = {
  short:'ngắn', medium:'trung', long:'dài', very_long:'rất dài',
  fast:'nhanh', normal:'thường', slow:'chậm', very_slow:'rất chậm',
  early_morning:'sáng sớm', morning_rush:'sáng cao điểm', noon:'trưa',
  afternoon:'chiều', evening_rush:'tan tầm', night:'tối', late_night:'đêm khuya',
  weekday:'ngày thường', weekend:'cuối tuần', holiday:'lễ',
  smooth:'thông thoáng', moderate:'vừa', heavy:'nặng', jammed:'tắc',
  sunny:'nắng', cloudy:'mây', light_rain:'mưa nhẹ', heavy_rain:'mưa to', storm:'bão',
  cool:'mát', comfortable:'dễ chịu', hot:'nóng', very_hot:'rất nóng',
  good:'tốt', unhealthy:'kém', hazardous:'nguy hại',
  low:'thấp', high:'cao', very_high:'rất cao',
  scarce:'rất ít', few:'ít', abundant:'nhiều',
  none:'không', mild:'nhẹ', strong:'mạnh', severe:'nghiêm trọng',
};

const fmtVnd = n => new Intl.NumberFormat('vi-VN').format(Math.round(n)) + 'đ';

let curves = null, charts = {}, debounceTimer = null;
let selectedFrom = null, selectedTo = null, mapRef = null, routeLayer = null;

/* ---------------- TABS ---------------- */
document.querySelectorAll('.tab').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const tg = btn.dataset.tab;
    document.querySelector(`.tab-panel[data-panel="${tg}"]`).classList.add('active');
    if (tg === 'fuzzy') setTimeout(drawAllCharts, 60);
  };
});

/* ---------------- VEHICLE ---------------- */
document.querySelectorAll('.vehicle input').forEach(r => {
  r.onchange = () => {
    document.querySelectorAll('.vehicle').forEach(v => v.classList.toggle('selected', v.contains(r) && r.checked));
    recalc();
  };
});

/* ---------------- DAY TYPE SEGMENT ---------------- */
document.querySelectorAll('#day_type-seg .seg-btn').forEach(b => {
  b.onclick = () => {
    document.querySelectorAll('#day_type-seg .seg-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    document.getElementById('day_type').value = b.dataset.val;
    debouncedRecalc();
  };
});

/* ---------------- SLIDERS ---------------- */
SLIDERS.forEach(s => {
  const el = document.getElementById(s.id);
  const out = document.getElementById(s.id + '-out');
  const upd = () => {
    out.textContent = s.fmt(parseFloat(el.value));
    debouncedRecalc();
  };
  el.addEventListener('input', upd);
  upd();
});

/* ---------------- PRESETS ---------------- */
document.querySelectorAll('.chip').forEach(c => c.onclick = () => {
  const p = c.dataset.preset;
  const set = (id, v) => {
    const el = document.getElementById(id);
    el.value = v; el.dispatchEvent(new Event('input'));
  };
  if (p === 'rush')  { set('traffic_level', 8.5); set('weather', 0.5); set('temperature', 32); set('air_quality', 130); }
  if (p === 'rain')  { set('traffic_level', 7.5); set('weather', 3.0); set('temperature', 26); set('air_quality', 90); }
  if (p === 'storm') { set('traffic_level', 9.5); set('weather', 3.9); set('temperature', 24); set('air_quality', 200); }
  if (p === 'clear') { set('traffic_level', 1.5); set('weather', 0.2); set('temperature', 27); set('air_quality', 50); }
});

/* ---------------- AUTO CONDITIONS ---------------- */
document.getElementById('auto-btn').onclick = async () => {
  const status = document.getElementById('auto-status');
  status.textContent = 'Đang lấy điều kiện hiện tại…';
  try {
    const r = await fetch('/api/auto-conditions');
    const d = await r.json();
    const apply = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== undefined) { el.value = val; el.dispatchEvent(new Event('input')); }
    };
    ['traffic_level','weather','temperature','air_quality',
     'demand_level','driver_availability','time_of_day'].forEach(k => apply(k, d[k]));
    document.querySelectorAll('#day_type-seg .seg-btn').forEach(b => {
      b.classList.toggle('active', parseInt(b.dataset.val,10) === d.day_type);
    });
    document.getElementById('day_type').value = d.day_type;
    status.textContent = `Đã cập nhật theo ${d.time}`;
    debouncedRecalc();
  } catch { status.textContent = 'Không lấy được dữ liệu.'; }
};

/* ---------------- CALCULATE ---------------- */
function debouncedRecalc() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(recalc, 90);
}

function getInputs() {
  const inp = {};
  ALL_INPUT_VARS.forEach(k => inp[k] = parseFloat(document.getElementById(k).value));
  inp.vehicle = document.querySelector('.vehicle input:checked').value;
  return inp;
}

async function recalc() {
  const payload = getInputs();
  try {
    const r = await fetch('/api/calculate', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const d = await r.json();
    if (d.error) return;
    renderResult(d, payload);
    updateCharts(payload, d);
  } catch (e) { console.error(e); }
}

function renderResult(d, p) {
  document.getElementById('r-fare').textContent = fmtVnd(d.final_fare);
  document.getElementById('r-base').textContent = fmtVnd(d.base_fare);
  document.getElementById('r-vehicle').textContent = `${d.icon} ${d.vehicle}`;
  document.getElementById('r-distance').textContent = `${p.distance.toFixed(1)} km`;
  document.getElementById('r-open').textContent = fmtVnd(d.open_fee);
  document.getElementById('r-perkm').textContent = fmtVnd(d.per_km) + '/km';

  const setMult = (id, v) => document.getElementById(id).textContent = `×${v.toFixed(2)}`;
  setMult('r-base-m', d.base_multiplier);
  setMult('r-env-m',  d.environment_factor);
  setMult('r-surge-m', d.surge_factor);
  setMult('r-total',  d.total_multiplier);
  setMult('r-total-num', d.total_multiplier);

  // bar (1.0 → 6.0 max realistic)
  const pct = Math.min(100, Math.max(5, ((d.total_multiplier - 1) / 4) * 100));
  document.getElementById('r-bar').style.width = pct + '%';

  // hero card sync
  const hf = document.getElementById('hero-from'); if (hf) hf.textContent = document.getElementById('from').value;
  const ht = document.getElementById('hero-to');   if (ht) ht.textContent = document.getElementById('to').value;
  document.getElementById('hero-dist').textContent = `${p.distance.toFixed(1)} km`;
  document.getElementById('hero-mult').textContent =
      `×${d.base_multiplier.toFixed(2)} × ${d.environment_factor.toFixed(2)} × ${d.surge_factor.toFixed(2)}`;
  document.getElementById('hero-fare').textContent = fmtVnd(d.final_fare);

  buildExplain(d);
}

function buildExplain(d) {
  const ul = document.getElementById('explain-list');
  ul.innerHTML = '';
  const items = [];
  for (const k of ALL_INPUT_VARS) {
    const m = d.memberships[k]; if (!m) continue;
    const top = Object.entries(m).sort((a,b) => b[1]-a[1])[0];
    if (top[1] < 0.05) continue;
    items.push(`<li><b>${VAR_LABELS[k]}</b> ≈ <span class="t">${TERM_VI[top[0]]||top[0]}</span> <small>(μ=${top[1].toFixed(2)})</small></li>`);
  }
  items.push(`<li class="sum">→ <b>Base</b> ×${d.base_multiplier.toFixed(2)} · <b>Env</b> ×${d.environment_factor.toFixed(2)} · <b>Surge</b> ×${d.surge_factor.toFixed(2)} = <b class="grad">×${d.total_multiplier.toFixed(2)}</b></li>`);
  ul.innerHTML = items.join('');
}

/* ---------------- CHARTS ---------------- */
async function loadCurves() {
  const r = await fetch('/api/membership-curves');
  curves = await r.json();
  buildChartContainers();
  drawAllCharts();
}

function buildChartContainers() {
  const host = document.getElementById('charts-container');
  host.innerHTML = '';
  ALL_VARS.forEach(v => {
    const w = document.createElement('div');
    w.className = 'chart-wrap';
    w.innerHTML = `<h5>${VAR_LABELS[v] || v}</h5><canvas id="chart-${v}"></canvas>`;
    host.appendChild(w);
  });
}

function drawAllCharts() {
  if (!curves) return;
  const inp = {};
  ALL_INPUT_VARS.forEach(k => inp[k] = parseFloat(document.getElementById(k).value));
  ALL_VARS.forEach(v => drawChart(v, inp[v]));
}

function drawChart(varName, value) {
  const c = curves[varName];
  if (!c) return;
  const palette = ['#a78bfa','#22d3ee','#f472b6','#34d399','#fbbf24','#fb7185','#60a5fa'];
  const datasets = Object.entries(c.terms).map(([label, mf], i) => ({
    label: TERM_VI[label] || label,
    data: c.universe.map((x, j) => ({ x, y: mf[j] })),
    borderColor: palette[i % palette.length],
    backgroundColor: palette[i % palette.length] + '33',
    borderWidth: 2, tension: 0.25, pointRadius: 0, fill: true,
  }));
  if (Number.isFinite(value)) {
    datasets.push({
      label: 'crisp',
      data: [{ x: value, y: 0 }, { x: value, y: 1 }],
      borderColor: '#fff', borderDash: [4,4], borderWidth: 1.5, pointRadius: 0,
    });
  }
  const ctx = document.getElementById('chart-' + varName);
  if (!ctx) return;
  if (charts[varName]) charts[varName].destroy();
  charts[varName] = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true, maintainAspectRatio: false, parsing: false,
      scales: {
        x: { type: 'linear', min: c.min, max: c.max, ticks: { color: '#94a3b8', font: { size: 10 } } },
        y: { min: 0, max: 1.05, ticks: { color: '#94a3b8', font: { size: 10 } } },
      },
      plugins: { legend: { labels: { color: '#cbd5e1', boxWidth: 8, font: { size: 10 } } } },
    },
  });
}

function updateCharts(p, d) {
  if (!curves || !Object.keys(charts).length) return;
  ALL_INPUT_VARS.forEach(k => drawChart(k, p[k]));
  drawChart('base_multiplier',    d.base_multiplier);
  drawChart('environment_factor', d.environment_factor);
  drawChart('surge_factor',       d.surge_factor);
}

/* ---------------- AUTOCOMPLETE ---------------- */
function setupAutocomplete(inputId) {
  const inp = document.getElementById(inputId);
  const list = document.querySelector(`.suggest[data-for="${inputId}"]`);
  let timer = null;
  inp.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = inp.value.trim();
      const r = await fetch('/api/places?q=' + encodeURIComponent(q));
      const items = await r.json();
      list.innerHTML = items.map(it =>
        `<li data-name="${it.name}" data-lat="${it.lat}" data-lng="${it.lng}">
          <b>${it.name}</b><small>${it.district || ''}</small></li>`).join('');
      list.classList.toggle('show', items.length > 0);
    }, 120);
  });
  list.addEventListener('click', e => {
    const li = e.target.closest('li'); if (!li) return;
    inp.value = li.dataset.name;
    const obj = { name: li.dataset.name, lat: parseFloat(li.dataset.lat), lng: parseFloat(li.dataset.lng) };
    if (inputId === 'from') selectedFrom = obj; else selectedTo = obj;
    list.classList.remove('show');
  });
  document.addEventListener('click', e => { if (!list.contains(e.target) && e.target !== inp) list.classList.remove('show'); });
}
setupAutocomplete('from');
setupAutocomplete('to');

/* ---------------- ROUTE ---------------- */
document.getElementById('route-btn').onclick = autoRoute;
async function autoRoute() {
  const from = document.getElementById('from').value;
  const to   = document.getElementById('to').value;
  const r = await fetch('/api/route', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ from, to }),
  });
  if (!r.ok) { toast('Không tìm thấy địa điểm'); return; }
  const d = await r.json();
  selectedFrom = d.from; selectedTo = d.to;
  const distEl = document.getElementById('distance');
  distEl.value = d.distance_km; distEl.dispatchEvent(new Event('input'));
  const tEl = document.getElementById('estimated_time');
  tEl.value = d.estimated_min; tEl.dispatchEvent(new Event('input'));
  drawMapRoute(d);
  toast(`📍 ${d.distance_km} km · ~${Math.round(d.estimated_min)} phút`);
}

/* ---------------- MAP ---------------- */
function initMap() {
  mapRef = L.map('map', { zoomControl: false }).setView([10.776, 106.700], 12);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap & CARTO', maxZoom: 19,
  }).addTo(mapRef);
}
function drawMapRoute(d) {
  if (!mapRef) return;
  if (routeLayer) mapRef.removeLayer(routeLayer);
  const a = [d.from.lat, d.from.lng], b = [d.to.lat, d.to.lng];
  routeLayer = L.layerGroup([
    L.marker(a).bindPopup(d.from.name),
    L.marker(b).bindPopup(d.to.name),
    L.polyline([a, b], { color: '#a78bfa', weight: 4, dashArray: '6,8' }),
  ]).addTo(mapRef);
  mapRef.fitBounds(L.latLngBounds([a, b]).pad(0.4));
}

/* ---------------- BOOKING + HISTORY ---------------- */
document.getElementById('book').onclick = async () => {
  const payload = getInputs();
  payload.from_text = document.getElementById('from').value;
  payload.to_text   = document.getElementById('to').value;
  const r = await fetch('/api/bookings', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload),
  });
  const d = await r.json();
  if (d.id) { toast(`✅ Đã đặt chuyến #${d.id} · ${fmtVnd(d.final_fare)}`); loadHistory(); }
};

async function loadHistory() {
  const [list, stats] = await Promise.all([
    fetch('/api/bookings').then(r => r.json()),
    fetch('/api/stats').then(r => r.json()),
  ]);
  const sel = document.getElementById('history-stats');
  sel.innerHTML = `
    <div class="h-stat"><small>Số chuyến</small><b>${stats.count}</b></div>
    <div class="h-stat"><small>Tổng cước</small><b>${fmtVnd(stats.total)}</b></div>
    <div class="h-stat"><small>Surge TB</small><b>×${stats.avg_surge.toFixed(2)}</b></div>
    <div class="h-stat"><small>Quãng đường TB</small><b>${stats.avg_distance.toFixed(1)} km</b></div>`;
  const host = document.getElementById('history-list');
  if (!list.length) { host.innerHTML = '<div class="empty">Chưa có chuyến nào.</div>'; return; }
  host.innerHTML = list.map(b => `
    <div class="h-card">
      <div class="h-top">
        <span class="h-icon">${b.icon}</span>
        <div><b>${b.from_text || '?'}</b><small> → ${b.to_text || '?'}</small></div>
        <button class="x" data-id="${b.id}">×</button>
      </div>
      <div class="h-mid">
        <span>${b.vehicle_name}</span>
        <span>${b.inputs.distance} km</span>
        <span class="grad">×${b.total_multiplier.toFixed(2)}</span>
      </div>
      <div class="h-multi">
        <small>B ×${b.base_multiplier.toFixed(2)}</small>
        <small>E ×${b.environment_factor.toFixed(2)}</small>
        <small>S ×${b.surge_factor.toFixed(2)}</small>
      </div>
      <div class="h-bot">
        <small>${new Date(b.created_at).toLocaleString('vi-VN')}</small>
        <b>${fmtVnd(b.final_fare)}</b>
      </div>
    </div>`).join('');
  host.querySelectorAll('.x').forEach(btn => btn.onclick = async () => {
    await fetch('/api/bookings/' + btn.dataset.id, { method: 'DELETE' });
    loadHistory();
  });
}

/* ---------------- TOAST ---------------- */
function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast'; t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add('show'), 30);
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 2400);
}

/* ---------------- INIT ---------------- */
initMap();
loadCurves();
loadHistory();
recalc();
