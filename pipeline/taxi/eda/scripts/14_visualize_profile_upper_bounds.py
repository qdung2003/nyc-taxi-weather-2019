import json
from pipeline.services.paths import TAXI_DIR


output_dir = TAXI_DIR / "eda" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
input_file = output_dir / "13_profile_upper_bounds.json"
output_file = output_dir / "14_profile_upper_bounds.html"


def main():
    if not input_file.exists():
        raise FileNotFoundError(f"Input JSON not found: {input_file}")

    payload = json.loads(input_file.read_text(encoding="utf-8"))

    file_02 = output_dir / "02_check_duplicate.json"
    if file_02.exists():
        profile_02 = json.loads(file_02.read_text(encoding="utf-8"))
        ordered_cols = []
        for c in profile_02.get("low_duplicate_columns", []):
            if c["column_name"] != "airport_fee":
                ordered_cols.append(c["column_name"])
        for c in profile_02.get("high_duplicate_columns", []):
            if c["column_name"] != "airport_fee":
                ordered_cols.append(c["column_name"])

        col_dict = {c["column_name"]: c for c in payload.get("columns", [])}
        sorted_columns = []
        for col in ordered_cols:
            if col in col_dict:
                sorted_columns.append(col_dict[col])
        for c in payload.get("columns", []):
            if c["column_name"] not in ordered_cols and c["column_name"] != "airport_fee":
                sorted_columns.append(c)
        payload["columns"] = sorted_columns

    html_template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>EDA 14 - Profile Upper Bounds</title>
  <style>
    :root {
      --bg:#f6f8fc;
      --card:#ffffff;
      --ink:#1b2432;
      --muted:#5e6a7c;
      --line:#e2e8f0;
      --bar:#1d4ed8;
    }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Segoe UI, Tahoma, sans-serif; background:linear-gradient(180deg,#eaf2ff 0%, var(--bg) 60%); color:var(--ink); }
    .wrap { max-width: 1320px; margin: 18px auto; padding: 0 14px 24px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px; box-shadow:0 8px 24px rgba(0,0,0,0.04); }
    h1 { margin:0 0 6px; font-size:24px; }
    .muted { color:var(--muted); font-size:13px; }
    .kpis { display:grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap:10px; margin-top:12px; }
    .kpi { border:1px solid var(--line); border-radius:10px; padding:10px; background:#fbfdff; }
    .kpi .label { font-size:12px; color:var(--muted); }
    .kpi .val { font-size:18px; font-weight:700; margin-top:4px; }
    .tabbar { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
    .tab { border:1px solid #bfdbfe; background:#fff; color:#1e3a8a; padding:7px 10px; border-radius:10px; cursor:pointer; font-weight:600; font-size:12px; }
    .tab.active { background:#1d4ed8; color:#fff; border-color:#1d4ed8; }
    .subcard { border:1px solid var(--line); border-radius:12px; padding:10px; background:#fff; margin-top:12px; }
    .subhead { font-weight:700; margin-bottom:8px; }
    #chart { width:100%; border:1px solid var(--line); border-radius:10px; background:#fff; }
    table { width:100%; border-collapse:collapse; font-size:12px; margin-top:4px; }
    th, td { text-align:left; padding:6px; border-bottom:1px solid var(--line); vertical-align:top; }
    th { background:#f8fafc; }
    .chips { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
    .chip { font-size:12px; border:1px solid var(--line); border-radius:999px; padding:3px 9px; background:#fff; }
    @media (max-width: 760px) { .kpis { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>EDA 14 - Profile Upper Bounds</h1>
      <div class="kpis">
        <div class="kpi"><div class="label">Columns</div><div class="val" id="kCols"></div></div>
        <div class="kpi"><div class="label">Total Rows</div><div class="val" id="kRows"></div></div>
        <div class="kpi"><div class="label">Current Column</div><div class="val" id="kCurrent"></div></div>
      </div>
      <div class="tabbar" id="tabs"></div>
    </div>

    <div class="card" style="margin-top:12px;">
      <div class="subhead">Column Snapshot</div>
      <div class="chips" id="chips"></div>
      <div class="subcard">
        <div class="subhead" id="chartTitle">Distribution</div>
        <svg id="chart" viewBox="0 0 1040 252" preserveAspectRatio="xMidYMid meet"></svg>
        <table>
          <thead><tr><th id="valueHeader">Value</th><th>Count</th><th>Percent</th></tr></thead>
          <tbody id="bodyRows"></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const payload = JSON_PAYLOAD;
    const columns = payload.columns || [];
    const rangeCols = new Set(payload.range_columns || []);
    const locationCols = new Set(['PULocationID', 'DOLocationID']);
    const LINE_CHART_THRESHOLD = 50;
    let current = 0;

    const fmtInt = (n) => Number(n || 0).toLocaleString();
    const fmtPct = (n) => `${Number(n || 0).toFixed(5)}%`;

    function setHeader() {
      document.getElementById('kCols').textContent = fmtInt(payload.summary?.column_count || columns.length);
      document.getElementById('kRows').textContent = fmtInt(payload.summary?.total_rows || 0);
    }

    function renderTabs() {
      const box = document.getElementById('tabs');
      box.innerHTML = '';
      columns.forEach((c, i) => {
        const btn = document.createElement('button');
        btn.className = 'tab' + (i === current ? ' active' : '');
        btn.textContent = c.column_name;
        btn.addEventListener('click', () => { current = i; render(); });
        box.appendChild(btn);
      });
    }

    function renderChips(c) {
      const chips = document.getElementById('chips');
      chips.innerHTML = '';
      const add = (label) => {
        const el = document.createElement('span');
        el.className = 'chip';
        el.textContent = label;
        chips.appendChild(el);
      };

      add(`type_value: ${c?.type_value ?? 'unknown'}`);
      if (c?.month_bucket_count != null) {
        add(`month_bucket_count: ${c.month_bucket_count}`);
      } else if (c?.range_bucket_count != null) {
        add(`range_bucket_count: ${c.range_bucket_count}`);
      } else {
        add(`unique_count: ${c?.unique_count ?? 'N/A'}`);
      }
      const ctp = (c?.correct_type_percent == null) ? 'N/A' : `${Number(c.correct_type_percent).toFixed(2)}%`;
      add(`correct_type_percent: ${ctp}`);
    }

    function renderTable(c) {
      const body = document.getElementById('bodyRows');
      body.innerHTML = '';
      const rows = c.chart_rows || [];

      if (!rows.length) {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="3">No distribution data for this column.</td>';
        body.appendChild(tr);
        return;
      }

      rows.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><code>${row.label}</code></td><td>${fmtInt(row.count)}</td><td>${fmtPct(row.percent)}</td>`;
        body.appendChild(tr);
      });
    }

    function renderChart(c) {
      const svg = document.getElementById('chart');
      while (svg.firstChild) svg.removeChild(svg.firstChild);

      const bins = c.chart_rows || [];
      const NS = 'http://www.w3.org/2000/svg';
      const mk = (name, attrs={}) => {
        const el = document.createElementNS(NS, name);
        Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, String(v)));
        return el;
      };

      const W = 1040, H = 252;
      const margin = { top: 16, right: 16, bottom: 34, left: 80 };
      const plotW = W - margin.left - margin.right;
      const plotH = H - margin.top - margin.bottom;

      svg.appendChild(mk('rect', { x: 0, y: 0, width: W, height: H, fill: '#fff' }));

      if (!bins.length) {
        const t = mk('text', { x: W/2, y: H/2, 'text-anchor': 'middle', fill: '#64748b', 'font-size': 13 });
        t.textContent = 'No chart data for this column.';
        svg.appendChild(t);
        return;
      }

      const maxY = Math.max(1, ...bins.map(b => b.count));
      const yScaleMax = maxY * 1.12;
      for (let i = 0; i <= 5; i++) {
        const yv = yScaleMax * (i / 5);
        const y = margin.top + plotH - (yv / yScaleMax) * plotH;
        svg.appendChild(mk('line', { x1: margin.left, y1: y, x2: W - margin.right, y2: y, stroke: '#e2e8f0' }));
        const lab = mk('text', { x: margin.left - 8, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' });
        lab.textContent = Math.round(yv).toLocaleString();
        svg.appendChild(lab);
      }

      svg.appendChild(mk('line', { x1: margin.left, y1: margin.top + plotH, x2: W - margin.right, y2: margin.top + plotH, stroke: '#475569' }));
      svg.appendChild(mk('line', { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, stroke: '#475569' }));

      const useLineChart = bins.length > LINE_CHART_THRESHOLD;
      if (useLineChart) {
        const isRangeColumn = c && rangeCols.has(c.column_name);
        const denom = Math.max(1, bins.length - 1);
        const pointX = (idx) => margin.left + (idx / denom) * plotW;
        const pointY = (count) => margin.top + plotH - (count / yScaleMax) * plotH;

        const linePoints = bins.map((b, idx) => `${pointX(idx)},${pointY(b.count)}`).join(' ');
        const areaPoints = `
          ${margin.left},${margin.top + plotH}
          ${linePoints}
          ${margin.left + plotW},${margin.top + plotH}
        `.trim().replace(/\s+/g, ' ');

        svg.appendChild(mk('polygon', {
          points: areaPoints,
          fill: '#93c5fd',
          'fill-opacity': 0.25,
          stroke: 'none'
        }));

        svg.appendChild(mk('polyline', {
          points: linePoints,
          fill: 'none',
          stroke: '#1d4ed8',
          'stroke-width': 2
        }));

        bins.forEach((b, idx) => {
          const x = pointX(idx);
          const y = pointY(b.count);
          svg.appendChild(mk('circle', {
            cx: x,
            cy: y,
            r: bins.length > 80 ? 1.5 : 2.3,
            fill: '#1d4ed8',
            stroke: '#000000',
            'stroke-width': 0.8
          }));
        });

        const maxLabels = 14;
        const labelStep = Math.max(1, Math.ceil(bins.length / maxLabels));
        bins.forEach((b, idx) => {
          const mustShow = idx === 0 || idx === bins.length - 1 || idx % labelStep === 0;
          if (!mustShow) return;
          const x = pointX(idx);
          const rawLabel = String((isRangeColumn ? (b.x_label ?? '') : b.label) || '');
          const label = rawLabel.length > 14 ? rawLabel.slice(0, 13) + '…' : rawLabel;
          const lx = mk('text', {
            x,
            y: margin.top + plotH + 14,
            'text-anchor': 'middle',
            'font-size': 10,
            fill: '#475569'
          });
          lx.textContent = label;
          svg.appendChild(lx);
        });
      } else {
        const slotW = plotW / bins.length;
        const barW = Math.min(28, slotW * 0.7);
        const isRangeColumn = c && rangeCols.has(c.column_name);
        const isLocationColumn = c && locationCols.has(c.column_name);
        const maxLabels = isRangeColumn ? 6 : 999;
        const labelStep = Math.max(1, Math.ceil(bins.length / maxLabels));

        bins.forEach((b, idx) => {
          const xCenter = margin.left + idx * slotW + slotW / 2;
          const x = xCenter - barW / 2;
          const h = (b.count / yScaleMax) * plotH;
          const y = margin.top + plotH - h;

          svg.appendChild(mk('rect', { x, y, width: barW, height: h, fill: '#1d4ed8', rx: 3, ry: 3 }));

          const pctText = mk('text', {
            x: xCenter,
            y: Math.max(margin.top + 10, y - 6),
            'text-anchor': 'middle',
            'font-size': 9,
            fill: '#0f172a'
          });
          pctText.textContent = `${Number(b.percent || 0).toFixed(2)}%`;
          svg.appendChild(pctText);

          const mustShowLabel = !isRangeColumn || idx === 0 || idx === bins.length - 1 || idx % labelStep === 0;
          if (mustShowLabel) {
            const rawLabel = String((isRangeColumn ? (b.x_label ?? '') : b.label) || '');
            const label = rawLabel.length > 14 ? rawLabel.slice(0, 13) + '…' : rawLabel;
            const isOtherLabel = isLocationColumn && rawLabel.startsWith('Other (') && rawLabel.endsWith(')');
            if (isOtherLabel) {
              const t = mk('text', {
                x: xCenter,
                y: margin.top + plotH + 14,
                'text-anchor': 'middle',
                'font-size': 10,
                fill: '#475569'
              });
              const t1 = mk('tspan', { x: xCenter, dy: 0 });
              t1.textContent = 'Other';
              t.appendChild(t1);
              const t2 = mk('tspan', { x: xCenter, dy: 11 });
              t2.textContent = rawLabel.replace('Other ', '');
              t.appendChild(t2);
              svg.appendChild(t);
            } else {
              const lx = mk('text', {
                x: xCenter,
                y: margin.top + plotH + 14,
                'text-anchor': 'middle',
                'font-size': 10,
                fill: '#475569'
              });
              lx.textContent = label;
              svg.appendChild(lx);
            }
          }
        });
      }
    }

    function render() {
      const c = columns[current];
      document.getElementById('kCurrent').textContent = c?.column_name || '-';
      document.getElementById('chartTitle').textContent = `Distribution - ${c?.column_name || ''}`;
      document.getElementById('valueHeader').textContent = (c && rangeCols.has(c.column_name)) ? 'Range' : 'Value';
      renderTabs();
      renderChips(c);
      renderChart(c);
      renderTable(c);
    }

    setHeader();
    if (columns.length > 0) render();
  </script>
</body>
</html>
"""
    html = html_template.replace("JSON_PAYLOAD", json.dumps(payload, ensure_ascii=False))

    output_file.write_text(html, encoding="utf-8")
    print(f"Saved dashboard HTML: {output_file}")
