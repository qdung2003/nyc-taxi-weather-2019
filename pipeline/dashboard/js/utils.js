(function (D) {
  const NS = 'http://www.w3.org/2000/svg';
  const KPI_PCT_PATTERN = /(percentage|percent|_pct)$/i;
  const PROFILE_KPI_STEPS = ['02', '03', '05', '06', '07', '08'];
  const PROFILE_KPI_ORDER = {
    '02': ['warehouse_database_path', 'warehouse_db_path', 'table', 'raw_table', 'row_count', 'max_unique_values', 'low_unique_column_count', 'high_unique_column_count'],
    '03': ['tail_ratio', 'positive_bin_count', 'high_unique_column_count'],
    '05': ['raw_count', 'clean_count', 'removed_count', 'removed_percentage', 'rule_count'],
    '06': ['row_count', 'low_unique_column_count', 'high_unique_column_count'],
    '07': ['first_pass_bin_count', 'second_pass_bin_count', 'first_pass_threshold_percent', 'second_pass_threshold_percent', 'column_count'],
    '08': ['row_count', 'low_unique_column_count', 'high_unique_column_count'],
  };
  const LOCATION_COLUMNS = new Set(['PULocationID', 'DOLocationID']);
  const MONTH_LABELS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const fmtInt = (n) => Number(n || 0).toLocaleString();
  function fmtPct(n) {
    const value = Number(n);
    if (!Number.isFinite(value) || Math.abs(value) < 1e-12) return '0%';
    const rounded = Math.round(value * 100) / 100;
    if (Math.abs(rounded) < 1e-12) return '0%';
    return `${rounded.toFixed(2).replace(/\.?0+$/, '')}%`;
  }
  const esc = (v) =>
    String(v === null ? 'null' : (v ?? '')).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const displayLabel = (v) => String(v === null ? 'null' : (v ?? '')).replace(/_/g, ' ');
  const formatKpiValue = (k, v) => (KPI_PCT_PATTERN.test(String(k)) ? fmtPct(v) : v);
  const kvRowHtml = (k, v) => `<div class="k01-meta-row"><span class="kv-key">${esc(displayLabel(k))}:</span><span class="kv-value">${esc(formatKpiValue(k, v))}</span></div>`;
  const shortText = (v, max = 34) => {
    const text = String(v ?? '');
    return text.length > max ? `${text.slice(0, max - 1)}…` : text;
  };
  const byPercentDesc = (a, b) => Number(b.percent || 0) - Number(a.percent || 0);

  function isPrimitiveValue(value) {
    return value === null || ['string', 'number', 'boolean'].includes(typeof value);
  }

  function getPrimitiveEntries(record, excludedKeys = []) {
    const excluded = new Set(excludedKeys);
    return Object.entries(record || {}).filter(([key, value]) => !excluded.has(key) && isPrimitiveValue(value));
  }

  function q(root, id) {
    return root.querySelector(`#${id}`);
  }

  function mk(name, attrs = {}) {
    const el = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, String(v)));
    return el;
  }

  function renderInnerTabs(tabsEl, items, activeIndex, onPick) {
    if (!tabsEl) return;
    tabsEl.innerHTML = '';
    items.forEach((item, i) => {
      const tab = document.createElement('button');
      tab.className = `tab ${i === activeIndex ? 'active' : ''}`;
      tab.type = 'button';
      tab.textContent = displayLabel(item.column_name || item.label || `col_${i + 1}`);
      tab.setAttribute('aria-pressed', i === activeIndex ? 'true' : 'false');
      tab.onclick = () => onPick(i);
      tab.onkeydown = (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onPick(i);
        }
      };
      tabsEl.appendChild(tab);
    });
    balanceFlexRows(tabsEl, '.tab', 'tab-break');
  }

  function balanceFlexRows(container, itemSelector, breakClass) {
    if (!container) return;
    container.querySelectorAll(`.${breakClass}`).forEach((el) => el.remove());
    const items = Array.from(container.querySelectorAll(itemSelector));
    if (items.length <= 2) return;
    const firstTop = items[0].offsetTop;
    const wraps = items.some((item, index) => index > 0 && item.offsetTop > firstTop);
    if (!wraps) return;
    const totalWidth = items.reduce((sum, item) => sum + item.offsetWidth, 0);
    let runningWidth = 0;
    let firstRowCount = Math.ceil(items.length / 2);
    for (let i = 0; i < items.length - 1; i += 1) {
      runningWidth += items[i].offsetWidth;
      if (runningWidth >= totalWidth / 2) {
        const prevDiff = i > 0 ? Math.abs((runningWidth - items[i].offsetWidth) - totalWidth / 2) : Infinity;
        const currDiff = Math.abs(runningWidth - totalWidth / 2);
        firstRowCount = currDiff <= prevDiff ? i + 1 : i;
        break;
      }
    }
    firstRowCount = Math.max(1, Math.min(items.length - 1, firstRowCount));
    const br = document.createElement('span');
    br.className = breakClass;
    container.insertBefore(br, items[firstRowCount]);
  }

  function renderRows(tbody, rows, toHtml) {
    if (!tbody) return;
    tbody.innerHTML = rows.map(toHtml).join('');
  }

  function renderScalarChips(chips, item) {
    if (!chips || !isPlainObject(item)) return;
    const entries = getPrimitiveEntries(item, ['column_name']);
    const firstRowCount = Math.ceil(entries.length / 2);
    chips.style.removeProperty('--chip-cols');
    chips.classList.remove('chips-balanced');
    chips.innerHTML = entries
      .map(([key, value], index) => (
        `${index === firstRowCount && entries.length > 2 ? '<span class="chip-break"></span>' : ''}<span class="chip">${esc(displayLabel(key))}: ${esc(formatKpiValue(key, value))}</span>`
      ))
      .join('');
    balanceFlexRows(chips, '.chip', 'chip-break');
  }

  function isPlainObject(v) {
    return v !== null && typeof v === 'object' && !Array.isArray(v);
  }

  function renderPrimitiveKpis(root, data, step) {
    const kpis = root.querySelector('.kpis');
    if (!kpis || !isPlainObject(data)) return;
    kpis.classList.remove('kpis-inline', 'kpis-eda01-style');
    if (PROFILE_KPI_STEPS.includes(String(step))) {
      kpis.classList.add('kpis-inline', 'kpis-eda01-style');
    }
    const primitiveEntries = getPrimitiveEntries(data);
    if (!primitiveEntries.length) return;
    const preferred = PROFILE_KPI_ORDER[String(step || '')] || [];
    const byKey = Object.fromEntries(primitiveEntries);
    const ordered = [
      ...preferred.filter((k) => Object.prototype.hasOwnProperty.call(byKey, k)).map((k) => [k, byKey[k]]),
      ...primitiveEntries.filter(([k]) => !preferred.includes(k)),
    ];
    kpis.innerHTML = ordered.map(([k, v]) => kvRowHtml(k, v)).join('');
    balanceFlexRows(kpis, '.k01-meta-row', 'kpi-break');
  }

  function toSeriesRows(chartRows) {
    if (!chartRows) return [];
    const normalizeLabel = (v) => (v === null ? 'null' : v);
    if (Array.isArray(chartRows)) {
      return chartRows.map((r) => ({
        label: normalizeLabel(r.label ?? r.x_label ?? (r.value === null ? 'null' : r.value) ?? ''),
        value: r.value,
        y: Number(r.y ?? r.count ?? r.quantity ?? 0),
        percent: Number(r.percent ?? 0),
      }));
    }
    const labels = chartRows.x_labels || chartRows.labels || chartRows.values || [];
    const counts = chartRows.counts || chartRows.bin_counts || chartRows.quantity || [];
    const percentages = chartRows.percentages || chartRows.percents || chartRows.bin_percentages || chartRows.quantity_percent || [];
    const n = Math.max(labels.length, counts.length, percentages.length);
    const rows = [];
    for (let i = 0; i < n; i += 1) {
      rows.push({
        label: normalizeLabel(labels[i] ?? ''),
        value: labels[i],
        y: Number(counts[i] ?? 0),
        percent: Number(percentages[i] ?? 0),
      });
    }
    return rows;
  }

  function buildLowDistributionRows(col) {
    const values = Array.isArray(col.values) ? col.values : [];
    const counts = Array.isArray(col.counts) ? col.counts : (Array.isArray(col.quantity) ? col.quantity : []);
    const percentages = Array.isArray(col.percentages) ? col.percentages : (Array.isArray(col.quantity_percent) ? col.quantity_percent : []);
    const n = Math.min(values.length, counts.length, percentages.length);
    const rows = [];
    for (let i = 0; i < n; i += 1) {
      rows.push({
        label: values[i] === null ? 'null' : String(values[i]),
        value: values[i],
        count: Number(counts[i] ?? 0),
        percent: Number(percentages[i] ?? 0),
      });
    }

    const colName = col.column_name;
    const isLocationCol = LOCATION_COLUMNS.has(colName);
    const minPct = isLocationCol ? 1.0 : 0.0;
    const dropZeroPercent = rows.length > 20;
    const passMinPercent = (row) => (isLocationCol ? row.percent > minPct : row.percent >= minPct);

    const visible = dropZeroPercent
      ? rows.filter((r) => r.percent > 0 && passMinPercent(r))
      : rows.filter((r) => passMinPercent(r));
    const hidden = rows.filter((r) => !visible.includes(r));

    const sortKey = (row) => {
      const v = row.value;
      if (v === null) return [2, 0, row.label];
      if (typeof v === 'number') return [0, v, row.label];
      return [1, 0, row.label];
    };
    visible.sort((a, b) => {
      const ka = sortKey(a);
      const kb = sortKey(b);
      if (ka[0] !== kb[0]) return ka[0] - kb[0];
      if (ka[1] !== kb[1]) return ka[1] - kb[1];
      return String(ka[2]).localeCompare(String(kb[2]));
    });

    if (hidden.length) {
      const otherCount = hidden.reduce((acc, r) => acc + Number(r.count || 0), 0);
      const otherPercent = Math.round(hidden.reduce((acc, r) => acc + Number(r.percent || 0), 0) * 100000) / 100000;
      visible.push({
        label: `Other (${hidden.length} values)`,
        count: otherCount,
        percent: otherPercent,
      });
    }
    return visible;
  }

  function buildFullDistributionRows(col) {
    const values = Array.isArray(col.values) ? col.values : [];
    const counts = Array.isArray(col.counts) ? col.counts : [];
    const percentages = Array.isArray(col.percentages) ? col.percentages : [];
    const n = Math.min(values.length, counts.length, percentages.length);
    return Array.from({ length: n }, (_, i) => ({
      label: values[i] === null ? 'null' : String(values[i]),
      value: values[i],
      count: Number(counts[i] ?? 0),
      percent: Number(percentages[i] ?? 0),
    }));
  }

  function pctFromTotal(count, totalRows) {
    const t = Number(totalRows || 0);
    return t > 0 ? (Number(count || 0) * 100) / t : 0;
  }

  function buildEda03MonthRows(col, totalRows) {
    const counts = Array.isArray(col.month_counts) ? col.month_counts : [];
    const pcts = Array.isArray(col.month_percentages) ? col.month_percentages : [];
    return MONTH_LABELS.map((label, i) => ({
      label,
      count: Number(counts[i] ?? 0),
      percent: Number(pcts[i] ?? pctFromTotal(counts[i] ?? 0, totalRows)),
    }));
  }

  function buildEda03RangeRows(col, totalRows) {
    const edges = Array.isArray(col.bin_edges) ? col.bin_edges.map((v) => Number(v)) : [];
    const counts = Array.isArray(col.bin_counts) ? col.bin_counts.map((v) => Number(v)) : [];
    const pcts = Array.isArray(col.bin_percentages) ? col.bin_percentages.map((v) => Number(v)) : [];
    const rows = [];

    let left = 0;
    for (let i = 0; i < counts.length; i += 1) {
      const right = Number(edges[i] ?? left);
      rows.push({
        label: `(${left.toFixed(2)}, ${right.toFixed(2)}]`,
        x_label: right.toFixed(2),
        count: Number(counts[i] ?? 0),
        percent: Number(pcts[i] ?? pctFromTotal(counts[i] ?? 0, totalRows)),
      });
      left = right;
    }
    return rows;
  }

  function profileValueHeader(col, rangeCols) {
    if (col.month_counts || col.month_count != null) return 'Month';
    if (col.bin_edges || col.range_count != null || rangeCols.has(col.column_name)) return 'Range';
    return 'Value';
  }

  function buildProfileRowsForMode(col, totalRows, mode) {
    if (['06', '08'].includes(String(mode))) {
      if (col.month_counts && col.month_percentages) return toSeriesRows(buildEda03MonthRows(col, totalRows));
      if (col.bin_edges && col.bin_counts && col.bin_percentages) return toSeriesRows(buildEda03RangeRows(col, totalRows));
      if (LOCATION_COLUMNS.has(col.column_name)) return toSeriesRows(buildLowDistributionRows(col));
      return toSeriesRows(buildFullDistributionRows(col));
    }
    if (mode === '02') return toSeriesRows(buildLowDistributionRows(col));
    if (col.month_counts && col.month_percentages) return toSeriesRows(buildEda03MonthRows(col, totalRows));
    if (col.bin_edges && col.bin_counts && col.bin_percentages) return toSeriesRows(buildEda03RangeRows(col, totalRows));
    if (col.chart_rows) return toSeriesRows(col.chart_rows);
    if (col.values && col.counts && col.percentages) return toSeriesRows(buildLowDistributionRows(col));
    return toSeriesRows({
      labels: col.labels || col.month_labels || col.values || [],
      counts: col.counts || col.month_counts || col.bin_counts || [],
      percentages: col.percentages || col.month_percentages || col.bin_percentages || [],
    });
  }

  function prependRangeSummaryRows(rows, col, totalRows) {
    const nullRows = rows.filter((row) => String(row.label).toLowerCase() === 'null');
    const otherRows = rows.filter((row) => String(row.label).startsWith('Other ('));
    const dataRows = rows.filter((row) => {
      const label = String(row.label);
      return label.toLowerCase() !== 'null' && !label.startsWith('Other (');
    });
    if (!(col && col.bin_edges && col.bin_counts && col.bin_percentages)) {
      return [...otherRows, ...nullRows, ...dataRows];
    }
    const summaryKeys = [
      ['negative_count', `[${col.min_value ?? ''}, 0)`],
      ['zero_count', '0'],
      ['above_chart_max_value_count', `(${col.chart_max_value ?? ''}, ${col.max_value ?? ''}]`],
    ];
    const summaryRows = summaryKeys
      .filter(([key]) => Object.prototype.hasOwnProperty.call(col, key))
      .map(([key, label]) => {
        const count = Number(col[key] || 0);
        return {
          key,
          label,
          y: count,
          percent: pctFromTotal(count, totalRows),
        };
      })
      .filter((row) => !(row.key === 'negative_count' && Number(row.y || 0) === 0 && Number(col.min_value || 0) >= 0));
    return [...otherRows, ...nullRows, ...summaryRows, ...dataRows];
  }

  function buildRangeChartRows(rows, col, totalRows) {
    const baseVisibleCount = rows.filter((row) => {
      const label = String(row.label).trim();
      return label.toLowerCase() !== 'null'
        && !label.startsWith('Other (')
        && label !== '< 0'
        && label !== '<0';
    }).length;
    const visibleRows = rows.filter((row) => {
      const label = String(row.label).trim();
      return label.toLowerCase() !== 'null'
        && !label.startsWith('Other (')
        && label !== '< 0'
        && label !== '<0'
        && !(label === '0' && Number(row.percent || 0) > 50 && baseVisibleCount > 15);
    });
    if (!(col && col.bin_edges && col.bin_counts && col.bin_percentages)) return visibleRows;
    const chartRows = [];
    if (Object.prototype.hasOwnProperty.call(col, 'zero_count')) {
      const zeroCount = Number(col.zero_count || 0);
      const rangeTotalRows = Number(totalRows || 0)
        || Number(col.negative_count || 0)
          + Number(col.zero_count || 0)
          + Number(col.above_chart_max_value_count || 0)
          + (Array.isArray(col.bin_counts) ? col.bin_counts.reduce((sum, count) => sum + Number(count || 0), 0) : 0);
      const zeroPercent = pctFromTotal(zeroCount, rangeTotalRows);
      const chartPointCount = 1
        + (Array.isArray(col.bin_counts) ? col.bin_counts.length : 0)
        + (Object.prototype.hasOwnProperty.call(col, 'above_chart_max_value_count') ? 1 : 0);
      if (!(zeroPercent > 50 && chartPointCount > 15)) {
        chartRows.push({
          label: '0',
          y: zeroCount,
          percent: zeroPercent,
        });
      }
    }
    chartRows.push(...visibleRows.filter((row) => {
      const label = String(row.label);
      return label !== '= 0';
    }));
    if (Object.prototype.hasOwnProperty.call(col, 'above_chart_max_value_count')) {
      const aboveCount = Number(col.above_chart_max_value_count || 0);
      chartRows.push({
        label: String(col.max_value ?? ''),
        y: aboveCount,
        percent: pctFromTotal(aboveCount, totalRows),
      });
    }
    return chartRows;
  }

    Object.assign(D, {
      fmtInt,
      fmtPct,
      esc,
      displayLabel,
      formatKpiValue,
      kvRowHtml,
      shortText,
      byPercentDesc,
      q,
      mk,
      renderInnerTabs,
      balanceFlexRows,
      renderRows,
      renderScalarChips,
      isPlainObject,
      renderPrimitiveKpis,
      profileValueHeader,
      buildProfileRowsForMode,
      prependRangeSummaryRows,
      buildRangeChartRows,
    });
  })(window.Dashboard = window.Dashboard || {});
