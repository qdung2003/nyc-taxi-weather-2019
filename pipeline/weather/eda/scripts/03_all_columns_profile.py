import json
from pathlib import Path
from pipeline.services.paths import WEATHER_DIR


input_file = WEATHER_DIR / "eda" / "results" / "01_check_duplicate.json"
output_file = WEATHER_DIR / "eda" / "results" / "03_all_columns_profile.html"


def load_json(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def to_chart_rows(col):
    values = col.get("values", [])
    counts = col.get("quantity", [])
    percents = col.get("quantity_percent", [])

    rows = []
    for i in range(min(len(values), len(counts), len(percents))):
        value = values[i]
        rows.append(
            {
                "label": "null" if value is None else str(value),
                "value": value,
                "count": int(counts[i]),
                "percent": float(percents[i]),
            }
        )

    def sort_key(row):
        value = row.get("value")
        if value is None:
            return (2, 0.0, row["label"])
        if isinstance(value, (int, float)):
            return (0, float(value), row["label"])
        return (1, 0.0, str(value))

    return sorted(rows, key=sort_key)


def build_payload(report):
    columns = []
    for col in report.get("low_duplicate_columns", []):
        col_name = col.get("column_name")
        if col_name == "DATE":
            continue
        columns.append(
            {
                "column_name": col_name,
                "type_value": col.get("type_value"),
                "unique_count": int(col.get("unique_count", 0)),
                "correct_type_percent": float(col.get("correct_type_percent", 0)),
                "chart_rows": to_chart_rows(col),
            }
        )

    return {
        "summary": {
            "row_count": int(report.get("row_count", 0)),
            "column_count": len(columns),
        },
        "columns": columns,
    }


def main() -> None:
    report = load_json(input_file)
    payload = build_payload(report)

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>EDA 03 - Weather Columns Distribution</title>
  <style>
    :root {{
      --bg:#f6f8fc;
      --card:#ffffff;
      --ink:#1b2432;
      --muted:#5e6a7c;
      --line:#e2e8f0;
      --bar:#1d4ed8;
      --ok:#0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Segoe UI, Tahoma, sans-serif; background:linear-gradient(180deg,#eaf2ff 0%, var(--bg) 60%); color:var(--ink); }}
    .wrap {{ max-width: 1320px; margin: 18px auto; padding: 0 14px 24px; }}
    .card {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px; box-shadow:0 8px 24px rgba(0,0,0,0.04); }}
    h1 {{ margin:0 0 6px; font-size:24px; }}
    .kpis {{ display:grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap:10px; margin-top:12px; }}
    .kpi {{ border:1px solid var(--line); border-radius:10px; padding:10px; background:#fbfdff; }}
    .kpi .label {{ font-size:12px; color:var(--muted); }}
    .kpi .val {{ font-size:18px; font-weight:700; margin-top:4px; }}
    .tabbar {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }}
    .tab {{ border:1px solid #bfdbfe; background:#fff; color:#1e3a8a; padding:7px 10px; border-radius:10px; cursor:pointer; font-weight:600; font-size:12px; }}
    .tab.active {{ background:#1d4ed8; color:#fff; border-color:#1d4ed8; }}
    .chips {{ display:flex; gap:8px; flex-wrap:wrap; margin: 8px 0; }}
    .chip {{ font-size:12px; border:1px solid var(--line); border-radius:999px; padding:3px 9px; background:#fff; color:var(--muted); }}
    .chip.ok {{ border-color:#99f6e4; color:var(--ok); background:#f0fdfa; }}
    #chart {{ width:100%; border:1px solid var(--line); border-radius:10px; background:#fff; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }}
    th, td {{ text-align:left; padding:6px; border-bottom:1px solid var(--line); vertical-align:top; }}
    th {{ background:#f8fafc; }}
    @media (max-width: 760px) {{ .kpis {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>EDA 03 - Weather Columns Distribution</h1>
      <div class="kpis">
        <div class="kpi"><div class="label">Rows</div><div class="val" id="kRows"></div></div>
        <div class="kpi"><div class="label">Columns (exclude DATE)</div><div class="val" id="kCols"></div></div>
        <div class="kpi"><div class="label">Current Column</div><div class="val" id="kCurrent"></div></div>
      </div>
      <div class="tabbar" id="tabs"></div>
    </div>

    <div class="card" style="margin-top:12px;">
      <div class="chips" id="chips"></div>
      <svg id="chart" viewBox="0 0 1040 252" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead><tr><th>Value</th><th>Count</th><th>Percent</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </div>

  <script>
    const payload = {json.dumps(payload, ensure_ascii=False)};
    const columns = payload.columns || [];
    let current = 0;

    const fmtInt = (n) => Number(n || 0).toLocaleString();
    const fmtPct = (n) => `${{Number(n || 0).toFixed(2)}}%`;

    function renderTabs() {{
      const box = document.getElementById('tabs');
      box.innerHTML = '';
      columns.forEach((c, i) => {{
        const b = document.createElement('button');
        b.className = 'tab' + (i === current ? ' active' : '');
        b.textContent = c.column_name;
        b.addEventListener('click', () => {{ current = i; render(); }});
        box.appendChild(b);
      }});
    }}

    function renderChips(col) {{
      const box = document.getElementById('chips');
      box.innerHTML = '';

      const add = (text, cls='') => {{
        const el = document.createElement('span');
        el.className = 'chip ' + cls;
        el.textContent = text;
        box.appendChild(el);
      }};

      add(`type: ${{col.type_value}}`);
      add(`unique_count: ${{fmtInt(col.unique_count)}}`);
      add(`correct_type_percent: ${{fmtPct(col.correct_type_percent)}}`, 'ok');
    }}

    function renderTable(col) {{
      const body = document.getElementById('rows');
      body.innerHTML = '';
      const rows = col.chart_rows || [];
      if (!rows.length) {{
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="3">No data</td>';
        body.appendChild(tr);
        return;
      }}

      rows.forEach(r => {{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><code>${{r.label}}</code></td><td>${{fmtInt(r.count)}}</td><td>${{fmtPct(r.percent)}}</td>`;
        body.appendChild(tr);
      }});
    }}

    function renderChart(col) {{
      const svg = document.getElementById('chart');
      while (svg.firstChild) svg.removeChild(svg.firstChild);

      const bins = col.chart_rows || [];
      const NS = 'http://www.w3.org/2000/svg';
      const mk = (name, attrs={{}}) => {{
        const el = document.createElementNS(NS, name);
        Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, String(v)));
        return el;
      }};

      const W = 1040, H = 252;
      const margin = {{ top: 22, right: 16, bottom: 34, left: 80 }};
      const plotW = W - margin.left - margin.right;
      const plotH = H - margin.top - margin.bottom;

      svg.appendChild(mk('rect', {{ x: 0, y: 0, width: W, height: H, fill: '#fff' }}));
      if (!bins.length) return;

      const maxY = Math.max(1, ...bins.map(b => b.count));
      const yScaleMax = maxY * 1.5;

      const useLine = bins.length > 25;
      const hasNeg = bins.some(b => typeof b.value === 'number' && b.value < 0);
      const splitIdx = hasNeg ? bins.findIndex(b => typeof b.value === 'number' && b.value >= 0) : -1;
      const denom = Math.max(1, bins.length - 1);
      const getX = (idx) => margin.left + (idx / denom) * plotW;
      const getY = (count) => margin.top + plotH - (count / yScaleMax) * plotH;

      // Grid lines (solid)
      for (let i = 0; i <= 5; i++) {{
        const yv = yScaleMax * (i / 5);
        const y = getY(yv);
        svg.appendChild(mk('line', {{ x1: margin.left, y1: y, x2: W - margin.right, y2: y, stroke: '#e2e8f0' }}));
        const lab = mk('text', {{ x: margin.left - 8, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' }});
        lab.textContent = Math.round(yv).toLocaleString();
        svg.appendChild(lab);
      }}

      // Horizontal Baseline
      svg.appendChild(mk('line', {{ x1: margin.left, y1: margin.top + plotH, x2: W - margin.right, y2: margin.top + plotH, stroke: '#475569', 'stroke-width': 1 }}));
      svg.appendChild(mk('line', {{ x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, stroke: '#475569', 'stroke-width': 1 }}));

      // Vertical Zero Axis (Solid inside fill, Dashed above)
      if (hasNeg && splitIdx >= 0) {{
        const x0 = getX(splitIdx);
        const yCurve = getY(bins[splitIdx].count);
        // Under the curve: Solid
        svg.appendChild(mk('line', {{ x1: x0, y1: margin.top + plotH, x2: x0, y2: yCurve, stroke: '#475569', 'stroke-width': 1.2 }}));
        // Above the curve: Dashed (for aesthetics)
        svg.appendChild(mk('line', {{ x1: x0, y1: yCurve, x2: x0, y2: margin.top, stroke: '#94a3b8', 'stroke-dasharray': '4,3', 'stroke-width': 1 }}));
      }}

      if (useLine) {{
        if (hasNeg && splitIdx > 0) {{
          // Red area for negative
          const negBins = bins.slice(0, splitIdx + 1);
          const pts = negBins.map((b, i) => `${{getX(i)}},${{getY(b.count)}}`);
          const areaPts = `${{getX(0)}},${{margin.top + plotH}} ` + pts.join(' ') + ` ${{getX(splitIdx)}},${{margin.top + plotH}}`;
          svg.appendChild(mk('polygon', {{ points: areaPts, fill: '#fecaca', 'fill-opacity': 0.25, stroke: 'none' }}));

          // Blue area for positive
          const posBins = bins.slice(splitIdx);
          const pts2 = posBins.map((b, i) => `${{getX(i + splitIdx)}},${{getY(b.count)}}`);
          const areaPts2 = `${{getX(splitIdx)}},${{margin.top + plotH}} ` + pts2.join(' ') + ` ${{getX(bins.length - 1)}},${{margin.top + plotH}}`;
          svg.appendChild(mk('polygon', {{ points: areaPts2, fill: '#93c5fd', 'fill-opacity': 0.25, stroke: 'none' }}));

          // Red line
          const linePts = negBins.map((b, i) => `${{getX(i)}},${{getY(b.count)}}`).join(' ');
          svg.appendChild(mk('polyline', {{ points: linePts, fill: 'none', stroke: '#dc2626', 'stroke-width': 2 }}));

          // Blue line
          const linePts2 = posBins.map((b, i) => `${{getX(i + splitIdx)}},${{getY(b.count)}}`).join(' ');
          svg.appendChild(mk('polyline', {{ points: linePts2, fill: 'none', stroke: '#1d4ed8', 'stroke-width': 2 }}));
        }} else {{
          const strokeCol = hasNeg ? '#dc2626' : '#1d4ed8';
          const fillCol = hasNeg ? '#fecaca' : '#93c5fd';
          const pts = bins.map((b, idx) => `${{getX(idx)}},${{getY(b.count)}}`);
          const areaPts = `${{getX(0)}},${{margin.top + plotH}} ` + pts.join(' ') + ` ${{getX(bins.length - 1)}},${{margin.top + plotH}}`;
          svg.appendChild(mk('polygon', {{ points: areaPts, fill: fillCol, 'fill-opacity': 0.25, stroke: 'none' }}));
          svg.appendChild(mk('polyline', {{ points: pts.join(' '), fill: 'none', stroke: strokeCol, 'stroke-width': 2 }}));
        }}

        bins.forEach((b, idx) => {{
          svg.appendChild(mk('circle', {{
            cx: getX(idx),
            cy: getY(b.count),
            r: 2.2,
            fill: (typeof b.value === 'number' && Number(b.value) < 0) ? '#dc2626' : ((Number(b.value) === 0 && hasNeg) ? '#16a34a' : '#1d4ed8'),
            stroke: '#000000',
            'stroke-width': 0.7
          }}));
        }});

        const step = Math.max(1, Math.ceil(bins.length / 12));
        bins.forEach((b, idx) => {{
          if (idx !== 0 && idx !== bins.length - 1 && idx % step !== 0) return;
          const x = getX(idx);
          const label = String(b.label).slice(0, 12);
          const t = mk('text', {{ x, y: margin.top + plotH + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' }});
          t.textContent = label;
          svg.appendChild(t);
        }});
      }} else {{
        const slotW = plotW / bins.length;
        const barW = Math.min(28, slotW * 0.7);
        bins.forEach((b, idx) => {{
          const xCenter = margin.left + idx * slotW + slotW / 2;
          const x = xCenter - barW / 2;
          const h = (b.count / yScaleMax) * plotH;
          const y = margin.top + plotH - h;
          const isNegative = typeof b.value === 'number' && b.value < 0;
          svg.appendChild(mk('rect', {{ x, y, width: barW, height: h, fill: isNegative ? '#dc2626' : '#1d4ed8', rx: 3, ry: 3 }}));

          const tPct = mk('text', {{ x: xCenter, y: y - 6, 'text-anchor': 'middle', 'font-size': 9, fill: '#0f172a' }});
          tPct.textContent = Number(b.percent).toFixed(1) + '%';
          svg.appendChild(tPct);

          const label = String(b.label).length > 12 ? String(b.label).slice(0, 11) + '…' : String(b.label);
          const t = mk('text', {{ x: xCenter, y: margin.top + plotH + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' }});
          t.textContent = label;
          svg.appendChild(t);
        }});
      }}
    }}

    function render() {{
      const col = columns[current];
      document.getElementById('kRows').textContent = fmtInt(payload.summary?.row_count || 0);
      document.getElementById('kCols').textContent = fmtInt(payload.summary?.column_count || 0);
      document.getElementById('kCurrent').textContent = col?.column_name || '-';
      renderTabs();
      if (col) {{
        renderChips(col);
        renderChart(col);
        renderTable(col);
      }}
    }}

    if (columns.length) render();
  </script>
</body>
</html>
"""

    output_file.write_text(html, encoding="utf-8")
    print(f"Saved dashboard: {output_file}")


if __name__ == "__main__":
    main()
