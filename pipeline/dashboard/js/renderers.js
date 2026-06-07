(function (D) {
  const {
    q,
    esc,
    displayLabel,
    fmtInt,
    fmtPct,
    kvRowHtml,
    mk,
    balanceFlexRows,
    renderInnerTabs,
    renderScalarChips,
    isPlainObject,
    profileValueHeader,
    buildProfileRowsForMode,
    buildRangeChartRows,
    prependRangeSummaryRows,
    drawBars,
    drawStackedBars,
    byPercentDesc,
    renderRows,
  } = D;
function render01(root, data) {
  const kpis = root.querySelector('.kpis');
  const filesToggle = q(root, 'k01FilesToggle');
  const filesList = q(root, 'k01FilesList');
  const filesHead = q(root, 'k01FilesHead');
  const filesBody = q(root, 'k01FilesBody');
  const schemaHead = q(root, 'k01SchemaHead');
  const schemaBody = q(root, 'k01SchemaBody');
  const mismatchBody = q(root, 'k01MismatchBody');
  if (kpis) {
    kpis.classList.add('kpis-inline');
    const rows = Object.entries(data).filter(([, value]) => (
      value === null || ['string', 'number', 'boolean'].includes(typeof value)
    ));
    kpis.innerHTML = rows.map(([k, v]) => kvRowHtml(k, v)).join('');
    balanceFlexRows(kpis, '.k01-meta-row', 'kpi-break');
  }

  if (filesList && filesBody) {
    const fileRows = data.files_rows || [];
    const files = fileRows.map((row, idx) => ({
      index: row.index ?? idx + 1,
      file: row.file ?? row.file_name ?? '',
    }));
    const fileTable = filesBody.closest('table');
    const filesWrap = filesList.closest('.eda01-files');
    if (!files.length && filesWrap) filesWrap.classList.add('hidden');
    const fileHeaders = data.files_headers || ['index', 'file'];
    const renderFileList = () => {
      const availableWidth = filesList.parentElement?.clientWidth || filesList.clientWidth || 720;
      const cols = Math.max(1, Math.min(4, files.length || 1, Math.floor(availableWidth / 190) || 1));
      const rowsPerCol = Math.ceil(files.length / cols);
      const columns = Array.from({ length: cols }, (_, c) => {
        const start = c * rowsPerCol;
        return Array.from({ length: rowsPerCol }, (_, r) => {
          const idx = start + r;
          if (idx >= files.length) return null;
          return files[idx];
        });
      });
      if (fileTable) {
        fileTable.style.setProperty('--file-cols', String(cols));
        fileTable.style.setProperty('--file-index-total', `${cols * 52}px`);
      }
        if (filesHead) {
          const headerPair = [
            `<th>${esc(displayLabel(fileHeaders[0] ?? 'index'))}</th>`,
            `<th>${esc(displayLabel(fileHeaders[1] ?? 'file'))}</th>`,
          ].join('');
          filesHead.innerHTML = `<tr>${Array.from({ length: cols }, () => headerPair).join('')}</tr>`;
        }
      filesBody.innerHTML = Array.from({ length: rowsPerCol }, (_, r) => {
        const cells = columns.map((col) => col[r]);
        const tds = cells.map((cell) => (
          cell
            ? `<td>${esc(cell.index)}</td><td><code>${esc(cell.file)}</code></td>`
            : '<td></td><td></td>'
        )).join('');
        return `<tr>${tds}</tr>`;
      }).join('');
    };
    renderFileList();
    filesList.classList.add('hidden');
    if (filesToggle) filesToggle.textContent = `Show file list (${files.length})`;
    const onResize = () => {
      if (!filesList.classList.contains('hidden')) renderFileList();
    };
    filesList._renderFileList = renderFileList;
    filesList._onResize = onResize;
    D.cleanupStep = () => window.removeEventListener('resize', onResize);
  }
  if (filesToggle && filesList) {
    filesToggle.onclick = () => {
      const isHidden = filesList.classList.toggle('hidden');
      if (!isHidden && typeof filesList._renderFileList === 'function') {
        filesList._renderFileList();
        if (typeof filesList._onResize === 'function') window.addEventListener('resize', filesList._onResize);
      } else if (typeof filesList._onResize === 'function') {
        window.removeEventListener('resize', filesList._onResize);
      }
      filesToggle.textContent = isHidden
        ? `Show file list (${(data.files || []).length})`
        : `Hide file list (${(data.files || []).length})`;
    };
  }

  if (schemaBody) {
    const schemaHeaders = data.schema_headers || ['column name', 'parquet type', 'database type', 'match'];
    if (schemaHead) {
      schemaHead.innerHTML = schemaHeaders.map((header) => `<th>${esc(displayLabel(header))}</th>`).join('');
    }
    const schemaRows = data.schema_rows || [];
    schemaBody.innerHTML = schemaRows
      .map((row) => {
        const columnName = row.column_name ?? '';
        const referenceType = row.parquet_type ?? row.csv_type ?? '';
        const databaseType = row.database_type ?? '';
        return `<tr><td><code>${esc(columnName)}</code></td><td>${esc(referenceType)}</td><td>${esc(databaseType)}</td><td>${esc(row.match ?? '')}</td></tr>`;
      })
      .join('');
  }

  if (mismatchBody) {
    const mismatches = data.files_mismatches || [];
    const mismatchSection = mismatchBody.closest('.card.section');
    if (!mismatches.length) {
      mismatchBody.innerHTML = '';
      if (mismatchSection) mismatchSection.classList.add('hidden');
    } else {
      if (mismatchSection) mismatchSection.classList.remove('hidden');
      mismatchBody.innerHTML = mismatches
        .map((m) => `<tr><td>${esc(m.file_name ?? '')}</td><td><span class="status-badge mismatch">Mismatch</span> <code>${esc(JSON.stringify(m.file_mismatches ?? {}))}</code></td></tr>`)
        .join('');
    }
  }
}

// ===== JS riêng EDA 02/03/06/08 (profile style) =====
function renderProfileTab(root, data, mode) {
  const highCols = data.high_unique_columns || data.high_duplicate_columns || [];
  const lowCols = data.low_unique_columns || data.low_duplicate_columns || [];
  const cols = mode === '02'
    ? lowCols
    : mode === '03'
      ? highCols
      : [...lowCols, ...highCols];

  if (!cols.length) return;

  const summaryRows = data.summary?.total_rows || data.summary?.row_count || data.row_count || data.total_rows || 0;
  const tabs = root.querySelector('.js-tabs') || q(root, 'tabs');
  const chips = q(root, 'chips');
  const filterCard = root.querySelector('.profile-filter-card');
  const filterBox = root.querySelector('.profile-filter');
  const chartTitle = q(root, 'chartTitle');
  const valueHeader = q(root, 'valueHeader');
  const chart = q(root, 'chart');
  const bodyRows = q(root, 'bodyRows');

  let idx = 0;

  const rangeCols = new Set(data.range_columns || ['fare_amount', 'tip_amount', 'tolls_amount', 'total_amount', 'trip_distance']);

  function draw() {
    const c = cols[idx] || {};
    if (chartTitle) chartTitle.textContent = `Distribution - ${displayLabel(c.column_name || '')}`;
    if (valueHeader) valueHeader.textContent = profileValueHeader(c, rangeCols);

    if (tabs) {
      renderInnerTabs(tabs, cols, idx, (i) => {
        idx = i;
        draw();
      });
    }

    renderScalarChips(chips, c);
    if (filterBox) {
      const filterEntries = c && isPlainObject(c.filter) ? Object.entries(c.filter) : [];
      if (mode === '03' && filterEntries.length) {
        if (filterCard) filterCard.classList.remove('hidden');
        filterBox.classList.add('kpis-inline', 'kpis-eda01-style');
        filterBox.innerHTML = filterEntries.map(([k, v]) => kvRowHtml(k, v)).join('');
        balanceFlexRows(filterBox, '.k01-meta-row', 'kpi-break');
      } else {
        if (filterCard) filterCard.classList.add('hidden');
        filterBox.innerHTML = '';
      }
    }

    const rows = buildProfileRowsForMode(c, summaryRows, mode);
    const chartRows = buildRangeChartRows(rows, c, summaryRows);
    drawBars(chart, chartRows, {
      isRangeColumn: Boolean(c.bin_edges && c.bin_counts && c.bin_percentages) || rangeCols.has(c.column_name),
      splitAtZero: (
        (D.getCurrentDomain() === 'weather' && ['TMIN', 'TMAX', 'tmin', 'tmax'].includes(String(c.column_name)))
        || (D.getCurrentDomain() === 'feature' && String(c.column_name) === 'avg_temp')
      ),
      lineThreshold: 40,
      maxBarWidth: 28,
      barRatio: 0.7,
      alwaysShowPct: true,
    });

    if (bodyRows) {
      const tableRows = prependRangeSummaryRows(rows, c, summaryRows);
      renderRows(bodyRows, tableRows, (r) => `<tr><td><code>${esc(r.label)}</code></td><td>${fmtInt(r.y)}</td><td>${fmtPct(r.percent)}</td></tr>`);
    }
  }

  draw();
}

// ===== JS riêng EDA 04 =====
function render04(root, raw) {
  const list = Array.isArray(raw) ? raw : (raw.checks || []);
  const check1 = list.find((x) => x.check === 1) || {};
  const check2 = list.find((x) => x.check === 2) || {};
  const check3 = list.find((x) => x.check === 3) || {};
  const c1 = check1.columns || [];
  const c2 = check2.columns || [];
  const c3 = check3.columns || [];

  const kTotal = q(root, 'kTotal');
  const kPt3 = q(root, 'kPt3');
  const kPt4 = q(root, 'kPt4');
  const check1Desc = q(root, 'check1Desc');
  const check2Desc = q(root, 'check2Desc');
  const check3Desc = q(root, 'check3Desc');
  const check2RowCount = q(root, 'check2RowCount');
  const check3RowCount = q(root, 'check3RowCount');
  if (check1Desc) check1Desc.textContent = check1.description === null ? 'null' : (check1.description ?? '');
  if (check2Desc) check2Desc.textContent = check2.description === null ? 'null' : (check2.description ?? '');
  if (check3Desc) check3Desc.textContent = check3.description === null ? 'null' : (check3.description ?? '');
  if (kTotal) {
    const c1Total = c1.reduce((acc, r) => acc + Number(r.total_count || 0), 0);
    const currentStepsData = D.dashboardData[D.getCurrentDomain()] || {};
    const fallbackTotal = currentStepsData['02']?.data?.row_count || currentStepsData['02']?.data?.total_rows || 0;
    kTotal.textContent = fmtInt(c1Total || fallbackTotal);
  }

  const rows1 = c1.map((r) => ({ label: `payment_type = ${r.payment_type}`, rows: r.tip_0_count || 0, totalCount: r.total_count || 0, percent: r.percent || 0 }));
  const rows2 = c2.map((r) => ({ label: r.column_name, rows: r.count || 0, rowCount: check2.row_count || 0, percent: r.percent || 0 }));
  const rows3 = c3.map((r) => ({ label: r.column_name, rows: r.count || 0, rowCount: check3.row_count || 0, percent: r.percent || 0 }));
  if (check2RowCount) check2RowCount.textContent = `payment_type = ${check2.payment_type ?? 3}: ${fmtInt(check2.row_count || 0)} rows`;
  if (check3RowCount) check3RowCount.textContent = `payment_type = ${check3.payment_type ?? 4}: ${fmtInt(check3.row_count || 0)} rows`;

  if (kPt3) kPt3.textContent = fmtInt(rows2.length ? Math.round((rows2[0].rows * 100) / Math.max(rows2[0].percent, 0.00001)) : 0);
  if (kPt4) kPt4.textContent = fmtInt(rows3.length ? Math.round((rows3[0].rows * 100) / Math.max(rows3[0].percent, 0.00001)) : 0);

  const eda04ChartOptions = { w: 1080, h: 320, maxBarWidth: 53, noTruncateLabels: true, margin: { top: 22, right: 24, bottom: 44, left: 72 } };
  const chartRows1 = rows1.map((r) => ({ label: r.label, y: r.percent, percent: r.percent }));
  const sortedRows2 = [...rows2].sort(byPercentDesc);
  const sortedRows3 = [...rows3].sort(byPercentDesc);
  const chartRows2 = sortedRows2.map((r) => ({ label: r.label, y: r.rows, percent: r.percent }));
  const chartRows3 = sortedRows3.map((r) => ({ label: r.label, y: r.rows, percent: r.percent }));
  drawBars(q(root, 'chart1'), chartRows1, { ...eda04ChartOptions, color: '#d97706', yMax: 100, yScaleMax: 112, hideZeroTick: true });
  drawBars(q(root, 'chart2'), chartRows2, { ...eda04ChartOptions, color: '#0f766e', yMax: 100, yScaleMax: 112, hideZeroTick: true });
  drawBars(q(root, 'chart3'), chartRows3, { ...eda04ChartOptions, color: '#7c3aed', yMax: 100, yScaleMax: 112, hideZeroTick: true });

  const tb1 = q(root, 'tb1');
  const tb2 = q(root, 'tb2');
  const tb3 = q(root, 'tb3');
  renderRows(tb1, rows1, (r) => `<tr><td><code>${esc(r.label)}</code></td><td>${fmtInt(r.rows)}</td><td>${fmtInt(r.totalCount)}</td><td>${fmtPct(r.percent)}</td></tr>`);
  renderRows(tb2, sortedRows2, (r) => `<tr><td><code>${esc(r.label)}</code></td><td>${fmtInt(r.rows)}</td><td>${fmtPct(r.percent)}</td></tr>`);
  renderRows(tb3, sortedRows3, (r) => `<tr><td><code>${esc(r.label)}</code></td><td>${fmtInt(r.rows)}</td><td>${fmtPct(r.percent)}</td></tr>`);
}

// ===== JS riêng EDA 05 (từ python 08) =====
function render05(root, data) {
  const summary = data.summary || data || {};
  const rules = data.rules || [];
  const pageSize = 8;
  let page = 0;

  const kpis = root.querySelector('.kpis');
  if (kpis) {
    kpis.classList.add('kpis-inline', 'kpis-eda01-style');
    const rows = [
      ['raw_count', summary.raw_count ?? summary.raw_row_count ?? summary.total_input_rows],
      ['clean_count', summary.clean_count ?? summary.clean_row_count ?? summary.total_clean_rows],
      ['removed_count', summary.removed_count ?? summary.removed_row_count ?? summary.total_removed_rows],
      ['removed_percentage', summary.removed_percentage ?? summary.total_removed_percent],
    ];
    kpis.innerHTML = rows.map(([k, v]) => kvRowHtml(k, v)).join('');
    balanceFlexRows(kpis, '.k01-meta-row', 'kpi-break');
  }

  const prevBtn = q(root, 'prevBtn');
  const nextBtn = q(root, 'nextBtn');
  const pageInfo = q(root, 'pageInfo');
  const rulesHead = q(root, 'rulesHead');
  const rulesBody = q(root, 'rulesBody');
  const svg = q(root, 'chart');
  const ruleRemovedCount = (r) =>
    Number(r.exclusive_removed_count ?? r.exclusive_removed_row_count ?? r.removed_exclusive_rows ?? 0)
    + Number(r.shared_removed_count ?? r.shared_removed_row_count ?? r.removed_shared_rows ?? 0);
  const sortedRules = [...rules].sort((a, b) => ruleRemovedCount(b) - ruleRemovedCount(a));

  if (rulesHead) {
    const headers = data.rules_headers || [
      'column_name',
      'rule_name',
      'invalid_count',
      'exclusive_removed_count',
      'shared_removed_count',
      'invalid_percentage',
      'exclusive_removed_percentage',
      'shared_removed_percentage',
    ];
    rulesHead.innerHTML = headers
      .map((header) => `<th>${esc(displayLabel(header))}</th>`)
      .join('');
  }

  function drawPage() {
    const totalPages = Math.max(1, Math.ceil(rules.length / pageSize));
    page = Math.max(0, Math.min(page, totalPages - 1));
    const items = sortedRules.slice(page * pageSize, page * pageSize + pageSize);

    if (pageInfo) pageInfo.textContent = `Page ${page + 1} / ${totalPages} - Showing ${items.length} rule(s)`;
    if (prevBtn) prevBtn.disabled = page === 0;
    if (nextBtn) nextBtn.disabled = page >= totalPages - 1;

    if (rulesBody) {
      renderRows(
        rulesBody,
        items,
        (r) =>
          `<tr><td><code>${esc(r.rule_name)}</code></td><td><code>${esc(r.column_name)}</code></td><td>${fmtInt(r.invalid_count ?? r.invalid_row_count)}</td><td>${fmtInt(r.exclusive_removed_count ?? r.exclusive_removed_row_count)}</td><td>${fmtInt(r.shared_removed_count ?? r.shared_removed_row_count)}</td><td>${fmtPct(r.invalid_percentage ?? r.invalid_row_percentage)}</td><td>${fmtPct(r.exclusive_removed_percentage)}</td><td>${fmtPct(r.shared_removed_percentage)}</td></tr>`,
      );
    }

    const chartRows = items.map((r) => ({
      label: r.column_name || r.rule_name,
      exclusive: Number(r.exclusive_removed_count ?? r.exclusive_removed_row_count ?? r.removed_exclusive_rows ?? 0),
      shared: Number(r.shared_removed_count ?? r.shared_removed_row_count ?? r.removed_shared_rows ?? 0),
      total: ruleRemovedCount(r),
      exclusivePercent: Number(r.exclusive_removed_percentage ?? 0),
      sharedPercent: Number(r.shared_removed_percentage ?? 0),
      percent: (r.exclusive_removed_percentage ?? 0) + (r.shared_removed_percentage ?? 0),
    }));
    drawStackedBars(svg, chartRows, {
      w: 1080,
      h: 320,
      maxBarWidth: 53,
      margin: { top: 22, right: 24, bottom: 44, left: 72 },
      noTruncateLabels: true,
    });
  }

  if (prevBtn) prevBtn.onclick = () => { page -= 1; drawPage(); };
  if (nextBtn) nextBtn.onclick = () => { page += 1; drawPage(); };
  drawPage();
}

// ===== JS riêng EDA 07 =====
function render07(root, data) {
  const cols = data.columns || [];
  if (!cols.length) return;
  const tabs = root.querySelector('.js-tabs') || q(root, 'tabs');
  const tbody = q(root, 'tbody');
  const chart = q(root, 'chart');
  const chips = q(root, 'chips');
  let idx = 0;

  function draw() {
    const col = cols[idx];
    const edges = col.bin_edges || [];
    const counts = col.bin_counts || [];
    const pcts = col.bin_percentages || [];
    const hasFullEdges = edges.length === counts.length + 1;
    const bins = counts.map((q, i) => {
        const left = hasFullEdges ? edges[i] : (i === 0 ? 0 : (edges[i - 1] ?? null));
        const right = hasFullEdges
          ? edges[i + 1]
          : edges[i] ?? col.second_pass_value ?? col.second_pass_max_value ?? col.final_upper_bound ?? null;
        return {
          index: i + 1,
          left,
          right,
          label: `(${left}, ${right}]`,
          quantity: q,
          quantity_percent: pcts[i] ?? 0,
        };
      });
    renderScalarChips(chips, col);

    if (tabs) {
      renderInnerTabs(tabs, cols, idx, (i) => {
        idx = i;
        draw();
      });
    }

    renderRows(tbody, bins, (b) => `<tr><td><code>${esc(b.label)}</code></td><td>${fmtInt(b.quantity)}</td><td>${fmtPct(b.quantity_percent)}</td></tr>`);

    drawBars(
      chart,
      bins.map((b) => ({ label: String(b.right), y: b.quantity, percent: b.quantity_percent, noLabelOffset: b.noLabelOffset })),
      { w: 1000, h: 280, isRangeColumn: true, noTruncateLabels: true, showAllLabels: true, alwaysShowPct: true, showVerticalDividers: true, xLabelOffsetRatio: 0.5, margin: { top: 22, right: 20, bottom: 42, left: 86 } },
    );
  }

  draw();
}

function drawFeatureMetricLine(svg, rows, metric) {
  if (!svg) return;
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const W = 1040;
  const H = 300;
  const margin = { top: 22, right: 24, bottom: 42, left: 86 };
  const plotW = W - margin.left - margin.right;
  const plotH = H - margin.top - margin.bottom;
  const values = rows.map((row) => Number(row[metric] ?? 0)).filter(Number.isFinite);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueSpan = Math.max(1e-9, maxValue - minValue);
  const splitAtZero = metric === 'avg_temp'
    && minValue < 0
    && maxValue > 0;
  const yScaleMin = splitAtZero
    ? minValue - Math.abs(minValue) * 0.12
    : minValue < 0
      ? minValue - valueSpan * 0.18
      : Math.max(0, minValue - valueSpan * 0.18);
  const yScaleMax = splitAtZero
    ? maxValue + Math.abs(maxValue) * 0.12
    : maxValue + valueSpan * 0.18;
  const yScaleSpan = Math.max(1e-9, yScaleMax - yScaleMin);
  const denom = Math.max(1, rows.length - 1);
  const pointX = (idx) => margin.left + (idx / denom) * plotW;
  const pointY = (value) => margin.top + plotH - ((Number(value || 0) - yScaleMin) / yScaleSpan) * plotH;
  const fmtNumber = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return '';
    return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  };

  svg.appendChild(mk('rect', { x: 0, y: 0, width: W, height: H, fill: '#fff' }));
  if (!rows.length) {
    const text = mk('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle', fill: '#64748b', 'font-size': 13 });
    text.textContent = 'No data.';
    svg.appendChild(text);
    return;
  }

  const yForTick = (value) => margin.top + plotH - ((value - yScaleMin) / yScaleSpan) * plotH;
  const yTicks = splitAtZero
    ? (() => {
        const yZero = yForTick(0);
        const minGap = 20;
        const buildSideTicks = (start, end, availableHeight) => {
          const segmentCount = Math.max(1, Math.min(6, Math.floor(availableHeight / 28)));
          return Array.from({ length: segmentCount }, (_, i) => start + (end - start) * (i / segmentCount));
        };
        const ticks = [
          ...buildSideTicks(yScaleMin, 0, margin.top + plotH - yZero),
          0,
          ...buildSideTicks(yScaleMax, 0, yZero - margin.top).reverse(),
        ];
        const used = [];
        return ticks.filter((tick) => {
          const y = yForTick(tick);
          if (tick !== 0 && Math.abs(y - yZero) < minGap) return false;
          if (used.some((usedY) => Math.abs(usedY - y) < minGap)) return false;
          used.push(y);
          return true;
        });
      })()
    : Array.from({ length: 6 }, (_, i) => yScaleMin + yScaleSpan * (i / 5));
  yTicks.forEach((yv) => {
    const y = yForTick(yv);
    if (splitAtZero && Math.abs(yv) < 1e-12) return;
    svg.appendChild(mk('line', { x1: margin.left, y1: y, x2: W - margin.right, y2: y, stroke: '#e2e8f0' }));
    const label = mk('text', { x: margin.left - 8, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' });
    label.textContent = fmtNumber(yv);
    svg.appendChild(label);
  });
  svg.appendChild(mk('line', { x1: margin.left, y1: margin.top + plotH, x2: W - margin.right, y2: margin.top + plotH, stroke: '#475569' }));
  svg.appendChild(mk('line', { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, stroke: '#475569' }));

  const points = rows.map((row, idx) => ({
    x: pointX(idx),
    y: pointY(row[metric]),
    prcp: row.prcp,
    value: row[metric],
  }));
  const baseY = margin.top + plotH;
  let zeroOverlayLine = null;
  let zeroOverlayLabel = null;
  if (splitAtZero) {
    const yZero = pointY(0);
    const drawSegmentFill = (a, b, fill) => {
      svg.appendChild(mk('polygon', {
        points: `${a.x},${yZero} ${a.x},${a.y} ${b.x},${b.y} ${b.x},${yZero}`,
        fill,
        'fill-opacity': 0.25,
        stroke: 'none',
      }));
    };
    const drawSegment = (a, b, stroke) => {
      svg.appendChild(mk('line', {
        x1: a.x,
        y1: a.y,
        x2: b.x,
        y2: b.y,
        fill: 'none',
        stroke,
        'stroke-width': 2,
        'stroke-linecap': 'butt',
      }));
    };
    for (let i = 1; i < points.length; i += 1) {
      const prev = points[i - 1];
      const point = points[i];
      const prevValue = Number(prev.value);
      const value = Number(point.value);
      if (!Number.isFinite(prevValue) || !Number.isFinite(value)) continue;
      if ((prevValue < 0 && value > 0) || (prevValue > 0 && value < 0)) {
        const ratio = (0 - prevValue) / (value - prevValue);
        const zeroPoint = {
          x: prev.x + (point.x - prev.x) * ratio,
          y: yZero,
        };
        drawSegmentFill(prev, zeroPoint, prevValue < 0 ? '#fecaca' : '#93c5fd');
        drawSegmentFill(zeroPoint, point, value < 0 ? '#fecaca' : '#93c5fd');
        drawSegment(prev, zeroPoint, prevValue < 0 ? '#dc2626' : '#1d4ed8');
        drawSegment(zeroPoint, point, value < 0 ? '#dc2626' : '#1d4ed8');
      } else {
        drawSegmentFill(prev, point, value < 0 || prevValue < 0 ? '#fecaca' : '#93c5fd');
        drawSegment(prev, point, value < 0 || prevValue < 0 ? '#dc2626' : '#1d4ed8');
      }
    }
    zeroOverlayLine = mk('line', {
      x1: margin.left,
      y1: yZero,
      x2: W - margin.right,
      y2: yZero,
      stroke: '#475569',
      'stroke-width': 1.4,
    });
    zeroOverlayLabel = mk('text', { x: margin.left - 8, y: yZero + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#475569', 'font-weight': 700 });
    zeroOverlayLabel.textContent = '0';
  } else {
    svg.appendChild(mk('polygon', {
      points: `${points[0].x},${baseY} ${points.map((p) => `${p.x},${p.y}`).join(' ')} ${points[points.length - 1].x},${baseY}`,
      fill: '#93c5fd',
      'fill-opacity': 0.25,
      stroke: 'none',
    }));
    svg.appendChild(mk('polyline', {
      points: points.map((p) => `${p.x},${p.y}`).join(' '),
      fill: 'none',
      stroke: '#1d4ed8',
      'stroke-width': 2,
    }));
  }
  points.forEach((point) => {
    const fill = splitAtZero && Number(point.value) < 0 ? '#dc2626' : '#1d4ed8';
    svg.appendChild(mk('circle', { cx: point.x, cy: point.y, r: rows.length > 80 ? 1.5 : 2.5, fill, stroke: '#0f172a', 'stroke-width': 0.7 }));
  });
  if (zeroOverlayLine) svg.appendChild(zeroOverlayLine);
  if (zeroOverlayLabel) svg.appendChild(zeroOverlayLabel);

  const labelStep = Math.max(1, Math.ceil(rows.length / 12));
  points.forEach((point, idx) => {
    if (!(idx === 0 || idx === points.length - 1 || idx % labelStep === 0)) return;
    const label = mk('text', { x: point.x, y: margin.top + plotH + 15, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' });
    label.textContent = String(rows[idx].date || point.prcp);
    svg.appendChild(label);
  });
}

function renderFeature02(root, data) {
  const buildRows = () => {
    if (Array.isArray(data.rows)) return data.rows;
    const dates = data.date || [];
    const prcp = data.prcp || [];
    const avgTemp = data.avg_temp || [];
    const tempRange = data.temp_range || [];
    const tripCount = data.trip_count || [];
    const avgDuration = data.avg_duration_minutes || [];
    const avgDistance = data.avg_trip_distance || [];
    const avgFare = data.avg_fare_amount || [];
    const avgTip = data.avg_tip_amount || [];
    const avgTotal = data.avg_total_amount || [];
    return dates.map((value, index) => ({
      date: value,
      prcp: prcp[index],
      avg_temp: avgTemp[index],
      temp_range: tempRange[index],
      trip_count: tripCount[index],
      avg_duration_minutes: avgDuration[index],
      avg_trip_distance: avgDistance[index],
      avg_fare_amount: avgFare[index],
      avg_tip_amount: avgTip[index],
      avg_total_amount: avgTotal[index],
    }));
  };
  const rows = buildRows();
  const metrics = [
    'trip_count',
    'prcp',
    'avg_temp',
    'temp_range',
    'avg_duration_minutes',
    'avg_trip_distance',
    'avg_fare_amount',
    'avg_tip_amount',
    'avg_total_amount',
  ];
  const tabs = root.querySelector('.js-tabs');
  const chart = q(root, 'chart');
  const chartTitle = q(root, 'chartTitle');
  const head = q(root, 'feature02Head');
  const body = q(root, 'feature02Body');
  let activeMetric = metrics[0];

  function draw() {
    const metricItems = metrics.map((metric) => ({ column_name: metric }));
    renderInnerTabs(tabs, metricItems, metrics.indexOf(activeMetric), (idx) => {
      activeMetric = metrics[idx];
      draw();
    });
    if (chartTitle) chartTitle.textContent = `${activeMetric} by date`;
    drawFeatureMetricLine(chart, rows, activeMetric);
    if (head) {
      head.innerHTML = ['date', activeMetric]
        .map((header) => `<th>${esc(header)}</th>`)
        .join('');
    }
    renderRows(
      body,
      rows,
      (row) => `
        <tr>
          <td>${esc(row.date)}</td>
          <td>${activeMetric === 'trip_count' ? fmtInt(row[activeMetric]) : esc(row[activeMetric])}</td>
        </tr>
      `,
    );
  }

  draw();
}

function drawFeatureCategoryBars(svg, rows, metric) {
  if (!svg) return;
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const W = 1040;
  const H = 300;
  const margin = { top: 22, right: 24, bottom: 54, left: 92 };
  const plotW = W - margin.left - margin.right;
  const plotH = H - margin.top - margin.bottom;
  const values = rows.map((row) => Number(row[metric] ?? 0)).filter(Number.isFinite);
  const maxY = Math.max(1, ...values) * 1.12;
  const slotW = plotW / Math.max(1, rows.length);
  const barW = Math.min(96, slotW * 0.58);
  const fmtNumber = (value) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

  svg.appendChild(mk('rect', { x: 0, y: 0, width: W, height: H, fill: '#fff' }));
  if (!rows.length) return;

  for (let i = 0; i <= 5; i += 1) {
    const yv = maxY * (i / 5);
    const y = margin.top + plotH - (yv / maxY) * plotH;
    svg.appendChild(mk('line', { x1: margin.left, y1: y, x2: W - margin.right, y2: y, stroke: '#e2e8f0' }));
    const yLabel = mk('text', { x: margin.left - 8, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' });
    yLabel.textContent = fmtNumber(yv);
    svg.appendChild(yLabel);
  }
  svg.appendChild(mk('line', { x1: margin.left, y1: margin.top + plotH, x2: W - margin.right, y2: margin.top + plotH, stroke: '#475569' }));
  svg.appendChild(mk('line', { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, stroke: '#475569' }));

  rows.forEach((row, index) => {
    const value = Number(row[metric] ?? 0);
    const xCenter = margin.left + index * slotW + slotW / 2;
    const height = (value / maxY) * plotH;
    const y = margin.top + plotH - height;
    const x = xCenter - barW / 2;
    svg.appendChild(mk('rect', { x, y, width: barW, height, fill: row.rain_status === 'rain' ? '#1d4ed8' : '#0f766e', rx: 3, ry: 3 }));
    const valueLabel = mk('text', { x: xCenter, y: Math.max(margin.top + 10, y - 6), 'text-anchor': 'middle', 'font-size': 10, fill: '#0f172a' });
    valueLabel.textContent = fmtNumber(value);
    svg.appendChild(valueLabel);
    const label = mk('text', { x: xCenter, y: margin.top + plotH + 16, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' });
    label.textContent = row.label;
    svg.appendChild(label);
  });
}

function buildFeatureCategoryRows(data, mode) {
  const count = Number(data.row_count || 0);
  return Array.from({ length: count }, (_, index) => {
    const dayType = data.day_type?.[index];
    const rainStatus = data.rain_status?.[index];
    const rainLevel = data.rain_level?.[index];
    const avgTempLevel = data.avg_temp_level?.[index];
    const tempRangeLevel = data.temp_range_level?.[index];
    const weatherLevel = avgTempLevel ?? tempRangeLevel;
    const valueRange = data.value_range?.[index];
    const formatLevelLabel = (level) => (valueRange ? `${level} ${valueRange}` : level);
    return {
      day_type: dayType,
      rain_status: rainStatus,
      rain_level: rainLevel,
      weather_level: weatherLevel,
      value_range: valueRange,
      label: mode === 'day_type_rain_status'
        ? `${dayType}/${rainStatus}`
        : mode === 'rain_level'
          ? formatLevelLabel(rainLevel)
          : mode === 'weather_level'
            ? formatLevelLabel(weatherLevel)
            : rainStatus,
      day_count: data.day_count?.[index],
      avg_trip_count: data.avg_trip_count?.[index],
      avg_duration_minutes: data.avg_duration_minutes?.[index],
      avg_trip_distance: data.avg_trip_distance?.[index],
      avg_fare_amount: data.avg_fare_amount?.[index],
      avg_tip_amount: data.avg_tip_amount?.[index],
      avg_total_amount: data.avg_total_amount?.[index],
    };
  });
}

function renderFeatureCategoryPanel(root, sectionData, mode, ids, activeMetric, options = {}) {
  const rows = buildFeatureCategoryRows(sectionData, mode);
  const chart = q(root, ids.chart);
  const chartTitle = q(root, ids.title);
  const head = q(root, ids.head);
  const body = q(root, ids.body);

  const diffPct = (row) => {
    let baseline;
    if (mode === 'day_type_rain_status') {
      baseline = rows.find((item) => item.day_type === row.day_type && item.rain_status === 'no_rain');
    } else if (mode === 'rain_level') {
      baseline = rows.find((item) => item.rain_level === 'no_rain');
    } else if (mode === 'weather_level') {
      baseline = options.baselineLevel
        ? rows.find((item) => item.weather_level === options.baselineLevel)
        : rows[0];
    } else {
      baseline = rows.find((item) => item.rain_status === 'no_rain');
    }
    const baseValue = Number(baseline?.[activeMetric]);
    const value = Number(row[activeMetric]);
    if (!Number.isFinite(baseValue) || Math.abs(baseValue) < 1e-12 || !Number.isFinite(value)) return null;
    return ((value - baseValue) / baseValue) * 100;
  };

  if (chartTitle) chartTitle.textContent = `${activeMetric} comparison`;
  drawFeatureCategoryBars(chart, rows, activeMetric);
  const leadingHeaders = mode === 'day_type_rain_status'
    ? ['day_type', 'rain_status']
    : mode === 'rain_level'
      ? ['rain_level', 'value_range']
      : mode === 'weather_level'
        ? ['weather_level', 'value_range']
        : ['rain_status'];
  if (head) {
      head.innerHTML = [
        ...leadingHeaders,
        'day_count',
        activeMetric,
        'diff_from_baseline',
      ].map((header) => `<th>${esc(displayLabel(header))}</th>`).join('');
  }
  renderRows(body, rows, (row) => `
    <tr>
      ${mode === 'day_type_rain_status' ? `<td>${esc(row.day_type)}</td>` : ''}
      <td>${esc(mode === 'rain_level' ? row.rain_level : mode === 'weather_level' ? row.weather_level : row.rain_status)}</td>
      ${mode === 'rain_level' || mode === 'weather_level' ? `<td>${esc(row.value_range)}</td>` : ''}
      <td>${fmtInt(row.day_count)}</td>
      <td>${activeMetric === 'avg_trip_count' ? fmtInt(row[activeMetric]) : esc(row[activeMetric])}</td>
      <td>${diffPct(row) === null ? '' : fmtPct(diffPct(row))}</td>
    </tr>
  `);
}

function renderFeature03Combined(root, data) {
  const weatherColumns = data.weather_columns || ['prcp', 'avg_temp', 'temp_range'];
  const metrics = [
    'avg_trip_count',
    'avg_duration_minutes',
    'avg_trip_distance',
    'avg_fare_amount',
    'avg_tip_amount',
    'avg_total_amount',
  ];
  const weatherTabs = q(root, 'feature03WeatherTabs');
  const metricTabs = q(root, 'feature03MetricTabs');
  const rainStatusSection = q(root, 'rainStatusSection');
  const rainWeekendSection = q(root, 'rainWeekendSection');
  const weatherLevelSection = q(root, 'weatherLevelSection');
  const summarySection = q(root, 'feature03SummarySection');
  const weatherLevelHeading = q(root, 'weatherLevelHeading');
  let activeWeather = weatherColumns[0] || 'prcp';
  let activeMetric = metrics[0];
  const drawMetricPanels = () => {
    renderInnerTabs(weatherTabs, weatherColumns.map((column) => ({ column_name: column })), weatherColumns.indexOf(activeWeather), (idx) => {
      activeWeather = weatherColumns[idx];
      drawMetricPanels();
    });
    renderInnerTabs(metricTabs, metrics.map((metric) => ({ column_name: metric })), metrics.indexOf(activeMetric), (idx) => {
      activeMetric = metrics[idx];
      drawMetricPanels();
    });

    const isPrcp = activeWeather === 'prcp';
    if (rainStatusSection) rainStatusSection.style.display = isPrcp ? '' : 'none';
    if (rainWeekendSection) rainWeekendSection.style.display = isPrcp ? '' : 'none';
    if (summarySection) summarySection.style.display = isPrcp ? '' : 'none';
    if (weatherLevelSection) weatherLevelSection.style.display = '';

    if (isPrcp) {
      if (weatherLevelHeading) weatherLevelHeading.textContent = 'Rain Levels';
      renderFeatureCategoryPanel(root, data.rain_status || {}, 'rain_status', {
        title: 'rainStatusTitle',
        chart: 'rainStatusChart',
        head: 'rainStatusHead',
        body: 'rainStatusBody',
      }, activeMetric);
      renderFeatureCategoryPanel(root, data.rain_weekend || {}, 'day_type_rain_status', {
        title: 'rainWeekendTitle',
        chart: 'rainWeekendChart',
        head: 'rainWeekendHead',
        body: 'rainWeekendBody',
      }, activeMetric);
      renderFeatureCategoryPanel(root, data.rain_level || {}, 'rain_level', {
        title: 'rainLevelTitle',
        chart: 'rainLevelChart',
        head: 'rainLevelHead',
        body: 'rainLevelBody',
      }, activeMetric);
      return;
    }

    const levelKey = activeWeather === 'avg_temp' ? 'avg_temp_level' : 'temp_range_level';
    if (weatherLevelHeading) weatherLevelHeading.textContent = `${activeWeather} Levels`;
    renderFeatureCategoryPanel(root, data[levelKey] || {}, 'weather_level', {
      title: 'rainLevelTitle',
      chart: 'rainLevelChart',
      head: 'rainLevelHead',
      body: 'rainLevelBody',
    }, activeMetric, {
      baselineLevel: activeWeather === 'avg_temp' ? 'mild_low_temp' : null,
    });
  };
  drawMetricPanels();

  const summary = data.impact_summary || {};
  const body = q(root, 'feature03SummaryBody');
  const rows = (summary.metric || []).map((metric, index) => ({
    metric,
    rain_pct: summary.rain_pct?.[index],
    weekday_rain_pct: summary.weekday_rain_pct?.[index],
    weekend_rain_pct: summary.weekend_rain_pct?.[index],
    light_rain_pct: summary.light_rain_pct?.[index],
    medium_rain_pct: summary.medium_rain_pct?.[index],
    heavy_rain_pct: summary.heavy_rain_pct?.[index],
  }));
  const pctCell = (value) => (value === null || value === undefined ? '' : fmtPct(value));
  renderRows(body, rows, (row) => `
    <tr>
      <td><code>${esc(row.metric)}</code></td>
      <td>${pctCell(row.rain_pct)}</td>
      <td>${pctCell(row.weekday_rain_pct)}</td>
      <td>${pctCell(row.weekend_rain_pct)}</td>
      <td>${pctCell(row.light_rain_pct)}</td>
      <td>${pctCell(row.medium_rain_pct)}</td>
      <td>${pctCell(row.heavy_rain_pct)}</td>
    </tr>
  `);
}

const STEP_RENDERERS = {
  '01': render01,
  '02': (root, data) => renderProfileTab(root, data, '02'),
  '03': (root, data) => renderProfileTab(root, data, '03'),
  '04': render04,
  '05': render05,
  '06': (root, data) => renderProfileTab(root, data, '06'),
  '07': render07,
  '08': (root, data) => renderProfileTab(root, data, '08'),
};


  Object.assign(D, {
    render01,
    renderProfileTab,
    render04,
    render05,
    render07,
    renderFeature02,
    renderFeature03Combined,
    STEP_RENDERERS,
  });
})(window.Dashboard = window.Dashboard || {});
