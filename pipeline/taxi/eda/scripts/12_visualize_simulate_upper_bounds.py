import json
from pipeline.services.paths import TAXI_DIR


output_dir = TAXI_DIR / "eda" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
input_file = output_dir / "11_simulate_upper_bounds.json"
output_file = output_dir / "12_simulate_upper_bounds.html"


def main() -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input JSON not found: {input_file}")

    payload = json.loads(input_file.read_text(encoding="utf-8"))

    html_template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>EDA 12 - Simulate Upper Bounds</title>
  <style>
    :root {
      --bg:#f7fafc;
      --card:#ffffff;
      --ink:#1f2937;
      --muted:#6b7280;
      --line:#e5e7eb;
    }
    * { box-sizing: border-box; }
    body { margin:0; font-family:Segoe UI, Tahoma, sans-serif; color:var(--ink); background:var(--bg); }
    .wrap { max-width:1280px; margin:18px auto; padding:0 14px 24px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px; }
    h1 { margin:0 0 8px; font-size:22px; }
    .muted { color:var(--muted); font-size:13px; }
    .tabs { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
    .tab { border:1px solid #93c5fd; background:#fff; color:#1e3a8a; border-radius:10px; padding:6px 10px; cursor:pointer; font-size:12px; font-weight:600; }
    .tab.active { background:#1d4ed8; color:#fff; border-color:#1d4ed8; }
    .grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:10px; }
    .kpi { border:1px solid var(--line); border-radius:10px; padding:8px; }
    .kpi .k { color:var(--muted); font-size:12px; }
    .kpi .v { margin-top:4px; font-size:18px; font-weight:700; }
    #chart { width:100%; border:1px solid var(--line); border-radius:10px; margin-top:12px; background:#fff; }
    table { width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }
    th, td { border-bottom:1px solid var(--line); padding:6px; text-align:left; }
    th { background:#f9fafb; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>EDA 12 - Simulate Upper Bounds</h1>
      <div class="muted">Pass1: 100 bins / 0.05% | Pass2: 10 bins / 0.5%</div>
      <div id="tabs" class="tabs"></div>
      <div class="grid">
        <div class="kpi"><div class="k">Column</div><div id="kCol" class="v">-</div></div>
        <div class="kpi"><div class="k">Final Upper Bound</div><div id="kUpper" class="v">-</div></div>
        <div class="kpi"><div class="k">Last Bin Percent</div><div id="kLastPct" class="v">-</div></div>
      </div>
      <svg id="chart" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead>
          <tr><th>Bin</th><th>Range</th><th>Quantity</th><th>Percent</th></tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>

  <script>
    const payload = JSON_PAYLOAD;
    const rows = payload.columns || [];
    let idx = 0;
    const fmtInt = n => Number(n || 0).toLocaleString();
    const fmtPct = n => `${Number(n || 0).toFixed(5)}%`;

    function renderTabs() {
      const tabs = document.getElementById('tabs');
      tabs.innerHTML = '';
      rows.forEach((r, i) => {
        const b = document.createElement('button');
        b.className = 'tab' + (i === idx ? ' active' : '');
        b.textContent = r.column_name;
        b.onclick = () => { idx = i; render(); };
        tabs.appendChild(b);
      });
    }

    function renderTable(col) {
      const body = document.getElementById('tbody');
      body.innerHTML = '';
      (col.expanded_bins || []).forEach(bin => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${bin.index}</td><td><code>(${bin.left}, ${bin.right}]</code></td><td>${fmtInt(bin.quantity)}</td><td>${fmtPct(bin.quantity_percent)}</td>`;
        body.appendChild(tr);
      });
    }

    function renderChart(col) {
      const svg = document.getElementById('chart');
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      const bins = col.expanded_bins || [];
      if (!bins.length) return;
      const NS = 'http://www.w3.org/2000/svg';
      const mk = (name, attrs={}) => {
        const el = document.createElementNS(NS, name);
        Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, String(v)));
        return el;
      };
      const W = 1000, H = 280;
      const margin = { top: 20, right: 20, bottom: 40, left: 80 };
      const plotW = W - margin.left - margin.right;
      const plotH = H - margin.top - margin.bottom;
      const maxY = Math.max(1, ...bins.map(x => x.quantity));
      const yMax = maxY * 1.12;
      svg.appendChild(mk('rect', { x:0, y:0, width:W, height:H, fill:'#fff' }));
      for (let i = 0; i <= 5; i++) {
        const yv = yMax * (i / 5);
        const y = margin.top + plotH - (yv / yMax) * plotH;
        svg.appendChild(mk('line', { x1:margin.left, y1:y, x2:W - margin.right, y2:y, stroke:'#e5e7eb' }));
      }
      svg.appendChild(mk('line', { x1:margin.left, y1:margin.top + plotH, x2:W-margin.right, y2:margin.top+plotH, stroke:'#64748b' }));
      svg.appendChild(mk('line', { x1:margin.left, y1:margin.top, x2:margin.left, y2:margin.top+plotH, stroke:'#64748b' }));
      const slotW = plotW / bins.length;
      const barW = Math.min(36, slotW * 0.72);
      bins.forEach((b, i) => {
        const xCenter = margin.left + i * slotW + slotW / 2;
        const h = (b.quantity / yMax) * plotH;
        const y = margin.top + plotH - h;
        const x = xCenter - barW / 2;
        svg.appendChild(mk('rect', { x, y, width:barW, height:h, fill:'#1d4ed8', rx:3, ry:3 }));
        const pct = mk('text', { x:xCenter, y:Math.max(margin.top+12, y-6), 'text-anchor':'middle', 'font-size':9, fill:'#111827' });
        pct.textContent = `${Number(b.quantity_percent || 0).toFixed(2)}%`;
        svg.appendChild(pct);
        const lx = mk('text', { x:xCenter, y:margin.top+plotH+14, 'text-anchor':'middle', 'font-size':10, fill:'#475569' });
        lx.textContent = String(b.index);
        svg.appendChild(lx);
      });
    }

    function render() {
      if (!rows.length) return;
      const col = rows[idx];
      const bins = col.expanded_bins || [];
      const lastPct = bins.length ? bins[bins.length - 1].quantity_percent : 0;
      document.getElementById('kCol').textContent = col.column_name || '-';
      document.getElementById('kUpper').textContent = String(col.final_upper_bound ?? col.max_value ?? '-');
      document.getElementById('kLastPct').textContent = fmtPct(lastPct);
      renderTabs();
      renderChart(col);
      renderTable(col);
    }
    render();
  </script>
</body>
</html>
"""
    html = html_template.replace("JSON_PAYLOAD", json.dumps(payload, ensure_ascii=False))

    output_file.write_text(html, encoding="utf-8")
    print(f"Saved HTML: {output_file}")
