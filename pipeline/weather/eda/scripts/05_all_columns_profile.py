import json
from pathlib import Path
from pipeline.services.paths import WEATHER_DIR


input_file = WEATHER_DIR / "eda" / "results" / "04_check_duplicate.json"
output_file = WEATHER_DIR / "eda" / "results" / "05_all_columns_profile.html"


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
  <title>EDA 05 - Weather Columns Distribution</title>
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
      <h1>EDA 05 - Weather Columns Distribution</h1>
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
    const tempCols = new Set(['TMIN', 'TMAX']);
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

      const isTempCol = tempCols.has(col.column_name);
      const maxY = Math.max(1, ...bins.map(b => b.count));
      const yScaleMax = maxY * 1.5;

      const numericTempValues = isTempCol
        ? bins.map(b => (typeof b.value === 'number' ? Number(b.value) : null)).filter(v => v !== null)
        : [];
      const hasTempScale = isTempCol && numericTempValues.length > 0;
      const minTempValue = hasTempScale ? Math.min(...numericTempValues) : 0;
      const maxTempValue = hasTempScale ? Math.max(...numericTempValues) : 0;
      const minTempScale = hasTempScale ? Math.min(minTempValue, 0) : 0;
      const maxTempScale = hasTempScale ? Math.max(maxTempValue, 0) : 0;
      const baseDenom = Math.max(1, bins.length - 1);

      const xForTempValue = (value) => {{
        if (!hasTempScale) return margin.left;
        const den = Math.max(1e-9, maxTempScale - minTempScale);
        return margin.left + ((value - minTempScale) / den) * plotW;
      }};

      const pointX = (idx) => {{
        if (hasTempScale && typeof bins[idx].value === 'number') return xForTempValue(Number(bins[idx].value));
        return margin.left + (idx / baseDenom) * plotW;
      }};
      const pointY = (count) => margin.top + plotH - (count / yScaleMax) * plotH;
      const lerp = (a, b, t) => a + (b - a) * t;

      // 1. Grid lines (solid)
      for (let i = 0; i <= 5; i++) {{
        const yv = yScaleMax * (i / 5);
        const y = pointY(yv);
        svg.appendChild(mk('line', {{ x1: margin.left, y1: y, x2: W - margin.right, y2: y, stroke: '#e2e8f0' }}));
        const lab = mk('text', {{ x: margin.left - 8, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' }});
        lab.textContent = Math.round(yv).toLocaleString();
        svg.appendChild(lab);
      }}

      svg.appendChild(mk('line', {{ x1: margin.left, y1: margin.top + plotH, x2: W - margin.right, y2: margin.top + plotH, stroke: '#475569', 'stroke-width': 1 }}));
      svg.appendChild(mk('line', {{ x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, stroke: '#475569', 'stroke-width': 1 }}));

      // Vertical Zero Axis (Solid inside fill, Dashed above)
      if (hasTempScale) {{
        const x00 = xForTempValue(0);
        let yCurve = margin.top + plotH;

        // Find or interpolate count at value 0
        const idxGreater = bins.findIndex(b => Number(b.value) >= 0);
        if (idxGreater === 0) {{
           yCurve = pointY(bins[0].count);
        }} else if (idxGreater > 0) {{
           const b1 = bins[idxGreater-1], b2 = bins[idxGreater];
           const v1 = Number(b1.value), v2 = Number(b2.value);
           const ratio = (0 - v1) / (v2 - v1);
           yCurve = lerp(pointY(b1.count), pointY(b2.count), ratio);
        }} else if (bins.length > 0) {{
           yCurve = pointY(bins[bins.length-1].count);
        }}

        // Solid part (Under the data curve)
        svg.appendChild(mk('line', {{ x1: x00, y1: margin.top + plotH, x2: x00, y2: yCurve, stroke: '#475569', 'stroke-width': 1.2 }}));
        // Dashed part (Above the data curve / Empty space)
        svg.appendChild(mk('line', {{ x1: x00, y1: yCurve, x2: x00, y2: margin.top, stroke: '#94a3b8', 'stroke-dasharray': '4,3', 'stroke-width': 1 }}));
      }}

      const useLine = bins.length > 25;
      if (useLine) {{
        const yBase = margin.top + plotH;
        const hasNeg = bins.some(b => typeof b.value === 'number' && Number(b.value) < 0);

        if (hasTempScale && hasNeg) {{
          let currentPath = [];
          let currentIsNeg = null;
          const x0 = xForTempValue(0);

          const closeSegment = (path, isNeg) => {{
            if (path.length < 2) return;
            // Area fill (Polygon)
            const polyPts = `${{path[0].split(',')[0]}},${{yBase}} ` + path.join(' ') + ` ${{path[path.length-1].split(',')[0]}},${{yBase}}`;
            svg.appendChild(mk('polygon', {{ points: polyPts, fill: isNeg ? '#fecaca' : '#93c5fd', 'fill-opacity': 0.25, stroke: 'none' }}));
            // Line (Polyline)
            svg.appendChild(mk('polyline', {{ points: path.join(' '), fill: 'none', stroke: isNeg ? '#dc2626' : '#1d4ed8', 'stroke-width': 2 }}));
          }};

          for (let i = 0; i < bins.length; i++) {{
            const v = Number(bins[i].value);
            const isNeg = v < 0;
            const px = pointX(i);
            const py = pointY(bins[i].count);

            if (currentIsNeg !== null && isNeg !== currentIsNeg) {{
              const vPrev = Number(bins[i-1].value);
              const ratio = (0 - vPrev) / (v - vPrev);
              const py0 = lerp(pointY(bins[i-1].count), py, ratio);
              currentPath.push(`${{x0}},${{py0}}`);
              closeSegment(currentPath, currentIsNeg);
              currentPath = [`${{x0}},${{py0}}`, `${{px}},${{py}}`];
            }} else {{
              currentPath.push(`${{px}},${{py}}`);
            }}
            currentIsNeg = isNeg;
          }}
          closeSegment(currentPath, currentIsNeg);
        }} else {{
          // Normal line chart or Temperature without negatives
          const pts = bins.map((b, idx) => `${{pointX(idx)}},${{pointY(b.count)}}`);
          const linePts = pts.join(' ');
          const polyPts = `${{pointX(0)}},${{yBase}} ` + linePts + ` ${{pointX(bins.length-1)}},${{yBase}}`;

          const isAllNeg = bins.every(b => typeof b.value === 'number' && Number(b.value) < 0);
          const fillCol = isAllNeg ? '#fecaca' : '#93c5fd';
          const strokeCol = isAllNeg ? '#dc2626' : '#1d4ed8';

          svg.appendChild(mk('polygon', {{ points: polyPts, fill: fillCol, 'fill-opacity': 0.25, stroke: 'none' }}));
          svg.appendChild(mk('polyline', {{ points: linePts, fill: 'none', stroke: strokeCol, 'stroke-width': 2 }}));
        }}

        // 3. Markers (Solid borders)
        const hasNegMarkers = bins.some(b => typeof b.value === 'number' && Number(b.value) < 0);
        bins.forEach((b, idx) => {{
          if (typeof b.value !== 'number') return;
          const v = Number(b.value);
          let fillColor = (v < 0) ? '#dc2626' : ((v === 0 && hasNegMarkers) ? '#16a34a' : '#1d4ed8');
          svg.appendChild(mk('circle', {{
            cx: pointX(idx),
            cy: pointY(b.count),
            r: 2.4,
            fill: fillColor,
            stroke: '#000000',
            'stroke-width': 0.7
          }}));
        }});

        // 4. Axis Labels
        if (hasTempScale) {{
          const formatTick = (v) => {{
            const n = Math.round(v * 10) / 10;
            return Number.isInteger(n) ? `${{n}}` : `${{n.toFixed(1)}}`;
          }};
          const buildTempTicks = () => {{
            const ticks = [];
            const totalSegments = 8;
            if (minTempScale < 0 && maxTempScale > 0) {{
              const negS = Math.max(2, Math.round(totalSegments * (Math.abs(minTempScale) / (maxTempScale - minTempScale))));
              const posS = totalSegments - negS;
              for(let i=0; i<=negS; i++) ticks.push(minTempScale + (0 - minTempScale) * (i/negS));
              for(let i=1; i<=posS; i++) ticks.push(0 + (maxTempScale - 0) * (i/posS));
              return ticks;
            }}
            for (let i = 0; i <= totalSegments; i++) ticks.push(minTempScale + (maxTempScale - minTempScale) * (i / totalSegments));
            return ticks;
          }};
          buildTempTicks().forEach((v) => {{
            const x = xForTempValue(v);
            const t = mk('text', {{ x, y: margin.top + plotH + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' }});
            t.textContent = formatTick(v);
            svg.appendChild(t);
          }});
        }}
      }} else {{
        // Bar charts with labels
        let barW = Math.min(28, (plotW / Math.max(1, bins.length)) * 0.7);
        bins.forEach((b, idx) => {{
          const xCenter = hasTempScale && typeof b.value === 'number'
            ? xForTempValue(Number(b.value))
            : margin.left + idx * (plotW / Math.max(1, bins.length)) + (plotW / Math.max(1, bins.length)) / 2;
          const x = xCenter - barW / 2;
          const h = (b.count / yScaleMax) * plotH;
          const y = margin.top + plotH - h;
          const isNegative = typeof b.value === 'number' && b.value < 0;
          svg.appendChild(mk('rect', {{ x, y, width: barW, height: h, fill: isNegative ? '#dc2626' : '#1d4ed8', rx: 3, ry: 3 }}));

          const tPct = mk('text', {{ x: xCenter, y: y - 6, 'text-anchor': 'middle', 'font-size': 9, fill: '#0f172a' }});
          tPct.textContent = Number(b.percent).toFixed(1) + '%';
          svg.appendChild(tPct);
        }});

        if (hasTempScale) {{
          const x0 = xForTempValue(0);
          // Find or interpolate count at value 0 (for the axis split)
          const idxGreater = bins.findIndex(b => Number(b.value) >= 0);
          let yCurve = margin.top + plotH;
          if (idxGreater === 0) {{ yCurve = pointY(bins[0].count); }}
          else if (idxGreater > 0) {{
             const b1 = bins[idxGreater-1], b2 = bins[idxGreater];
             const ratio = (0 - Number(b1.value)) / (Number(b2.value) - Number(b1.value));
             yCurve = lerp(pointY(b1.count), pointY(b2.count), ratio);
          }} else if (bins.length > 0) {{ yCurve = pointY(bins[bins.length-1].count); }}

          // Solid part (Under the data curve height)
          svg.appendChild(mk('line', {{ x1: x0, y1: margin.top + plotH, x2: x0, y2: yCurve, stroke: '#475569', 'stroke-width': 1.2 }}));
          // Dashed part (Above the data curve height)
          svg.appendChild(mk('line', {{ x1: x0, y1: yCurve, x2: x0, y2: margin.top, stroke: '#94a3b8', 'stroke-dasharray': '4,3', 'stroke-width': 1 }}));
        }}
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
