import json
from pipeline.services.paths import TAXI_DIR


output_dir = TAXI_DIR / "eda" / "results"
output_dir.mkdir(parents=True, exist_ok=True)
input_file = output_dir / "05_rate_payment_checks.json"
output_file = output_dir / "06_rate_payment_dashboard.html"


def main() -> None:
    if not input_file.exists():
        raise FileNotFoundError(f"Input report not found: {input_file}")

    report = json.loads(input_file.read_text(encoding="utf-8"))

    html_template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>EDA 06 - Payment_type Constraints</title>
  <style>
    :root {
      --bg:#f6f8fc;
      --card:#ffffff;
      --ink:#18212f;
      --muted:#5b6676;
      --line:#e2e8f0;
      --blue:#1d4ed8;
      --teal:#0f766e;
      --orange:#d97706;
      --violet:#7c3aed;
    }
    * { box-sizing:border-box; }
    body { margin:0; font-family:Segoe UI, Tahoma, sans-serif; background:linear-gradient(180deg,#eef4ff 0%, var(--bg) 60%); color:var(--ink); }
    .wrap { max-width:1240px; margin:18px auto; padding:0 14px 24px; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px; box-shadow:0 8px 24px rgba(0,0,0,0.04); }
    h1 { margin:0 0 8px; font-size:24px; }
    h2 { margin:0 0 8px; font-size:18px; }
    .muted { color:var(--muted); font-size:13px; }
    .grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:12px; }
    .kpi { border:1px solid var(--line); border-radius:10px; padding:10px; background:#fbfdff; }
    .kpi .label { font-size:12px; color:var(--muted); }
    .kpi .val { font-size:19px; font-weight:700; margin-top:4px; }
    .section { margin-top:12px; }
    #chart1, #chart2, #chart3 { width:100%; border:1px solid var(--line); border-radius:12px; background:#fff; }
    table { width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }
    th, td { text-align:left; border-bottom:1px solid var(--line); padding:8px; vertical-align:top; }
    th { background:#f8fafc; }
    @media (max-width:900px) { .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>EDA 06 - Payment_type Constraints</h1>
      <div class="grid">
        <div class="kpi"><div class="label">Total Rows</div><div class="val" id="kTotal"></div></div>
        <div class="kpi"><div class="label">Check 2 Denominator (payment_type = 3)</div><div class="val" id="kPt3"></div></div>
        <div class="kpi"><div class="label">Check 3 Denominator (payment_type = 4)</div><div class="val" id="kPt4"></div></div>
      </div>
    </div>

    <div class="card section">
      <h2>Check 1</h2>
      <div class="muted" id="check1Desc"></div>
      <svg id="chart1" viewBox="0 0 1080 320" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead><tr><th>Metric</th><th>Rows tip=0</th><th>Total rows theo payment_type</th><th>Percent</th></tr></thead>
        <tbody id="tb1"></tbody>
      </table>
    </div>

    <div class="card section">
      <h2>Check 2</h2>
      <div class="muted" id="check2Desc"></div>
      <svg id="chart2" viewBox="0 0 1080 390" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead><tr><th>Column</th><th>Rows (payment_type=3 &amp; col=0)</th><th>Percent</th></tr></thead>
        <tbody id="tb2"></tbody>
      </table>
    </div>

    <div class="card section">
      <h2>Check 3</h2>
      <div class="muted" id="check3Desc"></div>
      <svg id="chart3" viewBox="0 0 1080 390" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead><tr><th>Column</th><th>Rows (payment_type=4 &amp; col=0)</th><th>Percent</th></tr></thead>
        <tbody id="tb3"></tbody>
      </table>
    </div>
  </div>

  <script>
    const report = JSON_PAYLOAD;

    const fmtInt = (n) => Number(n || 0).toLocaleString();
    const fmtPct = (n) => `${Number(n || 0).toFixed(5)}%`;

    function mk(NS, name, attrs={}) {
      const el = document.createElementNS(NS, name);
      Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k, String(v)));
      return el;
    }

    function drawBarChart(svgId, rows, color, chartHeight=320) {
      const svg = document.getElementById(svgId);
      while (svg.firstChild) svg.removeChild(svg.firstChild);

      const NS = 'http://www.w3.org/2000/svg';
      const W = 1080;
      const H = chartHeight;
      const margin = { top: 24, right: 24, bottom: 64, left: 82 };
      const plotW = W - margin.left - margin.right;
      const plotH = H - margin.top - margin.bottom;
      const maxY = Math.max(1, ...rows.map(r => Number(r.percent || 0)));
      const yScaleMax = maxY * 1.12;

      svg.appendChild(mk(NS, 'rect', { x:0, y:0, width:W, height:H, fill:'#fff' }));

      for (let i = 0; i <= 5; i++) {
        const yv = yScaleMax * (i / 5);
        const y = margin.top + plotH - (yv / yScaleMax) * plotH;
        svg.appendChild(mk(NS, 'line', { x1:margin.left, y1:y, x2:W-margin.right, y2:y, stroke:'#e2e8f0' }));
        const t = mk(NS, 'text', { x:margin.left - 8, y:y + 4, 'text-anchor':'end', 'font-size':11, fill:'#64748b' });
        t.textContent = Number(yv).toFixed(1) + '%';
        svg.appendChild(t);
      }

      svg.appendChild(mk(NS, 'line', { x1:margin.left, y1:margin.top + plotH, x2:W-margin.right, y2:margin.top + plotH, stroke:'#475569' }));
      svg.appendChild(mk(NS, 'line', { x1:margin.left, y1:margin.top, x2:margin.left, y2:margin.top + plotH, stroke:'#475569' }));

      const slotW = plotW / Math.max(1, rows.length);
      const barW = Math.min(80, slotW * 0.66);

      rows.forEach((r, i) => {
        const xCenter = margin.left + i * slotW + slotW / 2;
        const h = (Number(r.percent || 0) / yScaleMax) * plotH;
        const y = margin.top + plotH - h;
        const x = xCenter - barW / 2;

        svg.appendChild(mk(NS, 'rect', { x, y, width:barW, height:h, fill:color, rx:4, ry:4 }));

        const pct = mk(NS, 'text', { x:xCenter, y:Math.max(margin.top + 10, y - 6), 'text-anchor':'middle', 'font-size':10, fill:'#0f172a' });
        pct.textContent = Number(r.percent || 0).toFixed(3) + '%';
        svg.appendChild(pct);

        const label = mk(NS, 'text', { x:xCenter, y:margin.top + plotH + 18, 'text-anchor':'middle', 'font-size':10, fill:'#475569' });
        label.textContent = r.label;
        svg.appendChild(label);
      });
    }

    function render() {
      const c1 = report.check_1_tip_eq_0_by_payment_type || {};
      const c2 = report.check_2_payment_type_3_zero_money_columns || {};
      const c3 = report.check_3_payment_type_4_zero_money_columns || {};

      document.getElementById('kTotal').textContent = fmtInt(report.summary?.total_rows || 0);
      document.getElementById('kPt3').textContent = fmtInt(c2.denominator_payment_type_3_rows || 0);
      document.getElementById('kPt4').textContent = fmtInt(c3.denominator_payment_type_4_rows || 0);

      document.getElementById('check1Desc').textContent = c1.description || 'Tip = 0 theo 4 muc payment_type (1, 2, 3, 4).';
      document.getElementById('check2Desc').textContent = c2.description || 'Trong nhom payment_type = 3, kiem tra ty le = 0 theo tung cot tien.';
      document.getElementById('check3Desc').textContent = c3.description || 'Trong nhom payment_type = 4, kiem tra ty le = 0 theo tung cot tien.';

      const rows1 = [
        {
          label: 'payment_type=1',
          rows: c1.col_1_payment_type_1?.rows_tip_eq_0 || 0,
          denom: c1.col_1_payment_type_1?.payment_type_total_rows || 0,
          percent: c1.col_1_payment_type_1?.percent || 0,
        },
        {
          label: 'payment_type=2',
          rows: c1.col_2_payment_type_2?.rows_tip_eq_0 || 0,
          denom: c1.col_2_payment_type_2?.payment_type_total_rows || 0,
          percent: c1.col_2_payment_type_2?.percent || 0,
        },
        {
          label: 'payment_type=3',
          rows: c1.col_3_payment_type_3?.rows_tip_eq_0 || 0,
          denom: c1.col_3_payment_type_3?.payment_type_total_rows || 0,
          percent: c1.col_3_payment_type_3?.percent || 0,
        },
        {
          label: 'payment_type=4',
          rows: c1.col_4_payment_type_4?.rows_tip_eq_0 || 0,
          denom: c1.col_4_payment_type_4?.payment_type_total_rows || 0,
          percent: c1.col_4_payment_type_4?.percent || 0,
        },
      ];
      drawBarChart('chart1', rows1, '#d97706', 320);
      const tb1 = document.getElementById('tb1');
      tb1.innerHTML = '';
      rows1.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><code>${r.label}</code></td><td>${fmtInt(r.rows)}</td><td>${fmtInt(r.denom)}</td><td>${fmtPct(r.percent)}</td>`;
        tb1.appendChild(tr);
      });

      const rows2 = (c2.columns || []).map(x => ({
        label: x.column_name,
        rows: x.rows_payment_type_3_and_col_eq_0 || 0,
        percent: x.percent || 0,
      }));
      drawBarChart('chart2', rows2, '#0f766e', 390);
      const tb2 = document.getElementById('tb2');
      tb2.innerHTML = '';
      rows2.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><code>${r.label}</code></td><td>${fmtInt(r.rows)}</td><td>${fmtPct(r.percent)}</td>`;
        tb2.appendChild(tr);
      });

      const rows3 = (c3.columns || []).map(x => ({
        label: x.column_name,
        rows: x.rows_payment_type_4_and_col_eq_0 || 0,
        percent: x.percent || 0,
      }));
      drawBarChart('chart3', rows3, '#7c3aed', 390);
      const tb3 = document.getElementById('tb3');
      tb3.innerHTML = '';
      rows3.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><code>${r.label}</code></td><td>${fmtInt(r.rows)}</td><td>${fmtPct(r.percent)}</td>`;
        tb3.appendChild(tr);
      });
    }

    render();
  </script>
</body>
</html>
"""
    html = html_template.replace("JSON_PAYLOAD", json.dumps(report, ensure_ascii=False))

    output_file.write_text(html, encoding="utf-8")
    print(f"Saved dashboard: {output_file}")
