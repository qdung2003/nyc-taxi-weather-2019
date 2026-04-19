import json
from pipeline.services.paths import TAXI_DIR


output_dir = TAXI_DIR / "eda" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
input_file = output_dir / "07_business_rules_impact.json"
output_file = output_dir / "08_business_rules_impact.html"

PAGE_SIZE = 8


def main() -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input report not found: {input_file}")

    report = json.loads(input_file.read_text(encoding="utf-8"))

    html_template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>EDA 08 - Business Rules Impact</title>
  <style>
    :root {
      --bg: #f6f8fb;
      --card: #ffffff;
      --ink: #18212f;
      --muted: #5b6676;
      --line: #e2e8f0;
      --c2: #0f766e;
      --c3: #d97706;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Segoe UI, Tahoma, sans-serif; background: linear-gradient(180deg, #eef4ff 0%, var(--bg) 60%); color: var(--ink); }
    .wrap { max-width: 1200px; margin: 20px auto; padding: 0 14px 24px; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px; box-shadow: 0 8px 24px rgba(0,0,0,0.04); }
    h1 { margin: 0 0 8px; font-size: 24px; }
    .muted { color: var(--muted); font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; margin-top: 12px; }
    .kpi { border: 1px solid var(--line); border-radius: 10px; padding: 10px; background: #fbfdff; }
    .kpi .label { font-size: 12px; color: var(--muted); }
    .kpi .val { font-size: 19px; font-weight: 700; margin-top: 4px; }
    .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin: 12px 0; flex-wrap: wrap; }
    .btns { display: flex; gap: 8px; }
    button { border: 1px solid #cbd5e1; background: #fff; padding: 8px 12px; border-radius: 9px; cursor: pointer; }
    button:disabled { opacity: 0.45; cursor: not-allowed; }
    .legend { display: flex; gap: 16px; font-size: 12px; color: var(--muted); margin: 8px 0 0; }
    .dot { width: 10px; height: 10px; display: inline-block; border-radius: 999px; margin-right: 6px; }
    #chart { width: 100%; border: 1px solid var(--line); border-radius: 12px; background: #fff; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 8px; vertical-align: top; }
    th { background: #f8fafc; }
    .small { font-size: 12px; color: var(--muted); }
    @media (max-width: 900px) { .grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
    @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } th:nth-child(4), td:nth-child(4), th:nth-child(6), td:nth-child(6) { display:none; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>EDA 08 - Business Rules Impact</h1>
      <div class="grid">
        <div class="kpi"><div class="label">Total Input Rows</div><div class="val" id="kpiInput"></div></div>
        <div class="kpi"><div class="label">Total Clean Rows</div><div class="val" id="kpiClean"></div></div>
        <div class="kpi"><div class="label">Total Removed Rows</div><div class="val" id="kpiRemoved"></div></div>
        <div class="kpi"><div class="label">Total Removed %</div><div class="val" id="kpiRemovedPct"></div></div>
      </div>
    </div>

    <div class="card" style="margin-top:12px;">
      <div class="toolbar">
        <div>
          <strong>Rules Chart (paged)</strong>
          <div class="small">Stacked bars per rule: Exclusive + Shared removed rows</div>
        </div>
        <div class="btns">
          <button id="prevBtn">Prev</button>
          <button id="nextBtn">Next</button>
        </div>
      </div>
      <div class="small" id="pageInfo"></div>
      <svg id="chart" viewBox="0 0 1100 430" preserveAspectRatio="xMidYMid meet"></svg>
      <div class="legend">
        <div><span class="dot" style="background:var(--c2);"></span>removed_exclusive_rows</div>
        <div><span class="dot" style="background:var(--c3);"></span>removed_shared_rows</div>
      </div>

      <table>
        <thead>
          <tr>
            <th>Rule</th>
            <th>Invalid Rows</th>
            <th>Invalid %</th>
            <th>Removed Exclusive</th>
            <th>Removed Shared</th>
          </tr>
        </thead>
        <tbody id="rulesBody"></tbody>
      </table>
    </div>
  </div>

  <script>
    const report = JSON_PAYLOAD;
    const rules = report.rules || [];
    const pageSize = PAGE_SIZE;
    let page = 0;

    function fmtInt(n) { return Number(n || 0).toLocaleString(); }
    function fmtPct(n) { return `${Number(n || 0).toFixed(5)}%`; }

    function setKpi() {
      const s = report.summary || {};
      document.getElementById('kpiInput').textContent = fmtInt(s.total_input_rows);
      document.getElementById('kpiClean').textContent = fmtInt(s.total_clean_rows);
      document.getElementById('kpiRemoved').textContent = fmtInt(s.total_removed_rows);
      document.getElementById('kpiRemovedPct').textContent = fmtPct(s.total_removed_percent);
    }

    function getPageItems() {
      const start = page * pageSize;
      return rules.slice(start, start + pageSize);
    }

    function renderTable(items) {
      const tbody = document.getElementById('rulesBody');
      tbody.innerHTML = '';
      items.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><code>${r.rule_name}</code></td>
          <td>${fmtInt(r.invalid_rows)}</td>
          <td>${fmtPct(r.invalid_percent_on_input)}</td>
          <td>${fmtInt(r.removed_exclusive_rows)}</td>
          <td>${fmtInt(r.removed_shared_rows)}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function renderChart(items) {
      const svg = document.getElementById('chart');
      while (svg.firstChild) svg.removeChild(svg.firstChild);

      const W = 1100, H = 430;
      const margin = { top: 24, right: 28, bottom: 110, left: 86 };
      const plotW = W - margin.left - margin.right;
      const plotH = H - margin.top - margin.bottom;

      const maxY = Math.max(1, ...items.map(d => (d.removed_exclusive_rows || 0) + (d.removed_shared_rows || 0)));
      const n = Math.max(1, items.length);
      const slotW = plotW / n;
      const barW = Math.min(56, slotW * 0.62);

      const NS = 'http://www.w3.org/2000/svg';
      const mk = (name, attrs={}) => {
        const el = document.createElementNS(NS, name);
        Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, String(v)));
        return el;
      };

      svg.appendChild(mk('rect', { x: 0, y: 0, width: W, height: H, fill: '#fff' }));

      for (let t = 0; t <= 5; t++) {
        const yVal = maxY * (t / 5);
        const y = margin.top + plotH - (yVal / maxY) * plotH;
        svg.appendChild(mk('line', { x1: margin.left, y1: y, x2: W - margin.right, y2: y, stroke: '#e2e8f0' }));
        const label = mk('text', { x: margin.left - 10, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' });
        label.textContent = Math.round(yVal).toLocaleString();
        svg.appendChild(label);
      }

      svg.appendChild(mk('line', { x1: margin.left, y1: margin.top + plotH, x2: W - margin.right, y2: margin.top + plotH, stroke: '#475569' }));
      svg.appendChild(mk('line', { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, stroke: '#475569' }));

      items.forEach((d, i) => {
        const ex = d.removed_exclusive_rows || 0;
        const sh = d.removed_shared_rows || 0;
        const xCenter = margin.left + i * slotW + slotW / 2;
        const x = xCenter - barW / 2;

        const exH = (ex / maxY) * plotH;
        const shH = (sh / maxY) * plotH;
        const yBase = margin.top + plotH;

        svg.appendChild(mk('rect', { x, y: yBase - exH, width: barW, height: exH, fill: '#0f766e', rx: 4, ry: 4 }));
        svg.appendChild(mk('rect', { x, y: yBase - exH - shH, width: barW, height: shH, fill: '#d97706', rx: 4, ry: 4 }));

        const total = ex + sh;
        const lab = mk('text', { x: xCenter, y: yBase - exH - shH - 6, 'text-anchor': 'middle', 'font-size': 11, fill: '#334155' });
        lab.textContent = total.toLocaleString();
        svg.appendChild(lab);

        const rawRule = String(d.rule_name || '');
        const rule = rawRule.length > 22 ? rawRule.slice(0, 21) + '…' : rawRule;
        const xLab = mk('text', { x: xCenter, y: margin.top + plotH + 16, 'text-anchor': 'end', 'font-size': 10, fill: '#475569', transform: `rotate(-35 ${xCenter} ${margin.top + plotH + 16})` });
        xLab.textContent = rule;
        svg.appendChild(xLab);
      });

      const yTitle = mk('text', { x: 20, y: margin.top - 6, 'font-size': 11, fill: '#64748b' });
      yTitle.textContent = 'Rows removed';
      svg.appendChild(yTitle);
    }

    function render() {
      const totalPages = Math.max(1, Math.ceil(rules.length / pageSize));
      page = Math.max(0, Math.min(page, totalPages - 1));
      const items = getPageItems();

      document.getElementById('pageInfo').textContent = `Page ${page + 1} / ${totalPages}  •  Showing ${items.length} rule(s)`;
      document.getElementById('prevBtn').disabled = page === 0;
      document.getElementById('nextBtn').disabled = page >= totalPages - 1;

      renderTable(items);
      renderChart(items);
    }

    document.getElementById('prevBtn').addEventListener('click', () => { page -= 1; render(); });
    document.getElementById('nextBtn').addEventListener('click', () => { page += 1; render(); });

    setKpi();
    render();
  </script>
</body>
</html>
"""
    html = html_template.replace("PAGE_SIZE", str(PAGE_SIZE))
    html = html.replace("JSON_PAYLOAD", json.dumps(report, ensure_ascii=False))

    output_file.write_text(html, encoding="utf-8")
    print(f"Saved dashboard: {output_file}")
