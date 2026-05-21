(function (D) {
  const { mk, fmtPct, shortText } = D;
function drawBars(svg, rows, opts = {}) {
  if (!svg) return;
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const W = opts.w || 1040;
  const H = opts.h || 252;
  const margin = opts.margin || { top: 16, right: 16, bottom: 34, left: 80 };
  const lineRightPad = rows.length > (opts.lineThreshold || 50) ? 18 : 0;
  const plotW = W - margin.left - margin.right - lineRightPad;
  const plotH = H - margin.top - margin.bottom;
  const chartValue = (row) => {
    const value = Number(row.percent ?? row.y ?? 0);
    return Number.isFinite(value) ? value : 0;
  };
  const maxY = Math.max(1, ...rows.map(chartValue));
  const yScaleMax = opts.yScaleMax ?? opts.yMax ?? maxY * 1.12;
  const yTickMax = opts.yMax ?? yScaleMax;
  const slotW = plotW / Math.max(1, rows.length);
  const barW = Math.min(opts.maxBarWidth || 28, slotW * (opts.barRatio || 0.7));
  const useLineChart = rows.length > (opts.lineThreshold || 50);
  const isRangeColumn = Boolean(opts.isRangeColumn);
  const numericValue = (row) => {
    const value = Number(row.value ?? row.label);
    return Number.isFinite(value) ? value : null;
  };
  const splitRowsAtZero = Boolean(opts.splitAtZero)
    && rows.some((row) => {
      const value = numericValue(row);
      return value !== null && value < 0;
    })
    && rows.some((row) => {
      const value = numericValue(row);
      return value !== null && value >= 0;
    });
  const numericValues = splitRowsAtZero
    ? rows.map(numericValue).filter((value) => value !== null)
    : [];
  const minSplitValue = splitRowsAtZero ? Math.min(0, ...numericValues) : 0;
  const maxSplitValue = splitRowsAtZero ? Math.max(0, ...numericValues) : 0;
  const axisLabel = (rawLabel) => {
    const raw = String(rawLabel ?? '');
    if (!isRangeColumn) return raw;
    if (raw.trim() === '< 0') return '<0';
    if (raw.trim() === '= 0') return '0';
    const m = raw.match(/^\(\s*[-\d.]+\s*,\s*([-\d.]+)\s*\]$/);
    if (m) return m[1];
    return raw;
  };

  svg.appendChild(mk('rect', { x: 0, y: 0, width: W, height: H, fill: '#fff' }));
  if (!rows.length) {
    const t = mk('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle', fill: '#64748b', 'font-size': 13 });
    t.textContent = 'No chart data for this column.';
    svg.appendChild(t);
    return;
  }

  const firstTick = opts.hideZeroTick ? 1 : 0;
  for (let i = firstTick; i <= 5; i += 1) {
    const yv = yTickMax * (i / 5);
    const y = margin.top + plotH - (yv / yScaleMax) * plotH;
    svg.appendChild(mk('line', { x1: margin.left, y1: y, x2: W - margin.right, y2: y, stroke: '#e2e8f0' }));
    const yLabel = mk('text', { x: margin.left - 8, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' });
    yLabel.textContent = fmtPct(yv);
    svg.appendChild(yLabel);
  }
  svg.appendChild(mk('line', { x1: margin.left, y1: margin.top + plotH, x2: W - margin.right, y2: margin.top + plotH, stroke: '#475569' }));
  svg.appendChild(mk('line', { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, stroke: '#475569' }));

  if (useLineChart) {
    const denom = Math.max(1, rows.length - 1);
    const pointX = (idx) => {
      if (splitRowsAtZero) {
        const value = numericValue(rows[idx]);
        if (value !== null) {
          const den = Math.max(1e-9, maxSplitValue - minSplitValue);
          return margin.left + ((value - minSplitValue) / den) * plotW;
        }
      }
      return margin.left + (idx / denom) * plotW;
    };
    const pointY = (v) => margin.top + plotH - (Number(v || 0) / yScaleMax) * plotH;
    const yBase = margin.top + plotH;
    const appendAreaLine = (points, fill, stroke) => {
      if (points.length < 2) return;
      const areaPoints = `${points[0].x},${yBase} ${points.map((p) => `${p.x},${p.y}`).join(' ')} ${points[points.length - 1].x},${yBase}`;
      svg.appendChild(mk('polygon', { points: areaPoints, fill, 'fill-opacity': 0.25, stroke: 'none' }));
      svg.appendChild(mk('polyline', { points: points.map((p) => `${p.x},${p.y}`).join(' '), fill: 'none', stroke, 'stroke-width': 2 }));
    };

    if (splitRowsAtZero) {
      const xZero = margin.left + ((0 - minSplitValue) / Math.max(1e-9, maxSplitValue - minSplitValue)) * plotW;
      let yZero = yBase;
      const points = rows.map((row, i) => ({
        x: pointX(i),
        y: pointY(chartValue(row)),
        value: numericValue(row),
      }));
      const negPoints = [];
      const posPoints = [];
      for (let i = 0; i < points.length; i += 1) {
        const point = points[i];
        if (point.value === null) continue;
        if (i > 0) {
          const prev = points[i - 1];
          if (prev.value !== null && prev.value < 0 && point.value >= 0) {
            const ratio = (0 - prev.value) / Math.max(1e-9, point.value - prev.value);
            yZero = prev.y + (point.y - prev.y) * ratio;
            const zeroPoint = { x: xZero, y: yZero, value: 0 };
            negPoints.push(zeroPoint);
            posPoints.push(zeroPoint);
          }
        }
        if (point.value < 0) negPoints.push(point);
        else posPoints.push(point);
      }
      appendAreaLine(negPoints, '#fecaca', '#dc2626');
      appendAreaLine(posPoints, '#93c5fd', opts.color || '#1d4ed8');
      svg.appendChild(mk('line', { x1: xZero, y1: yBase, x2: xZero, y2: yZero, stroke: '#475569', 'stroke-width': 1.2 }));
      svg.appendChild(mk('line', { x1: xZero, y1: yZero, x2: xZero, y2: margin.top, stroke: '#94a3b8', 'stroke-dasharray': '4,3', 'stroke-width': 1 }));
    } else {
      const linePoints = rows.map((r, i) => `${pointX(i)},${pointY(chartValue(r))}`).join(' ');
      const areaPoints = `${margin.left},${yBase} ${linePoints} ${margin.left + plotW},${yBase}`;
      svg.appendChild(mk('polygon', { points: areaPoints, fill: '#93c5fd', 'fill-opacity': 0.25, stroke: 'none' }));
      svg.appendChild(mk('polyline', { points: linePoints, fill: 'none', stroke: opts.color || '#1d4ed8', 'stroke-width': 2 }));
    }
    rows.forEach((r, i) => {
      const value = numericValue(r);
      const fill = splitRowsAtZero && value !== null && value < 0 ? '#dc2626' : (splitRowsAtZero && value === 0 ? '#16a34a' : opts.color || '#1d4ed8');
      svg.appendChild(mk('circle', { cx: pointX(i), cy: pointY(chartValue(r)), r: rows.length > 80 ? 1.5 : 2.3, fill, stroke: '#000000', 'stroke-width': 0.8 }));
    });
    if (splitRowsAtZero) {
      const xForValue = (value) => margin.left + ((value - minSplitValue) / Math.max(1e-9, maxSplitValue - minSplitValue)) * plotW;
      const formatTick = (value) => {
        const rounded = Math.round(value * 10) / 10;
        return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
      };
      const buildSideTicks = (start, end, availableWidth) => {
        const segmentCount = Math.max(1, Math.min(4, Math.floor(availableWidth / 90)));
        return Array.from({ length: segmentCount }, (_, i) => start + (end - start) * (i / segmentCount));
      };
      const xZero = xForValue(0);
      const minGap = 44;
      const ticks = [
        ...buildSideTicks(minSplitValue, 0, xZero - margin.left),
        0,
        ...buildSideTicks(maxSplitValue, 0, W - margin.right - xZero).reverse(),
      ];
      const used = [];
      ticks.forEach((tick) => {
        const x = xForValue(tick);
        if (tick !== 0 && Math.abs(x - xZero) < minGap) return;
        if (used.some((usedX) => Math.abs(usedX - x) < minGap)) return;
        used.push(x);
        const label = mk('text', { class: 'axis-edge-label', x, y: margin.top + plotH + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' });
        label.textContent = formatTick(tick);
        svg.appendChild(label);
      });
      return;
    }
    const maxLabels = 14;
    const labelStep = Math.max(1, Math.ceil(rows.length / maxLabels));
    rows.forEach((r, i) => {
      const raw = axisLabel(r.label ?? '');
      const isOtherLabel = raw.startsWith('Other (') && raw.endsWith(')');
      if (!(i === 0 || i === rows.length - 1 || i % labelStep === 0 || isOtherLabel)) return;
      const label = mk('text', { class: 'axis-edge-label', x: pointX(i), y: margin.top + plotH + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' });
      if (isOtherLabel) {
        const t1 = mk('tspan', { x: pointX(i), dy: 0 });
        t1.textContent = 'Other';
        label.appendChild(t1);
        const t2 = mk('tspan', { x: pointX(i), dy: 11 });
        t2.textContent = raw.replace('Other ', '');
        label.appendChild(t2);
      } else {
        label.textContent = raw.length > 14 ? `${raw.slice(0, 13)}…` : raw;
      }
      svg.appendChild(label);
    });
    return;
  }

  const maxLabels = isRangeColumn ? 6 : 999;
  const labelStep = Math.max(1, Math.ceil(rows.length / maxLabels));
  if (opts.showVerticalDividers) {
    for (let i = 1; i < rows.length; i += 1) {
      const x = margin.left + i * slotW;
      svg.appendChild(mk('line', { class: 'chart-vertical-divider', x1: x, y1: margin.top, x2: x, y2: margin.top + plotH, stroke: '#cbd5e1' }));
    }
    if (opts.firstDividerLabel && rows.length > 1) {
      const label = mk('text', {
        class: 'axis-edge-label',
        x: margin.left + slotW,
        y: margin.top + plotH + 14,
        'text-anchor': 'middle',
        'font-size': 10,
        fill: '#475569',
      });
      label.textContent = opts.firstDividerLabel;
      svg.appendChild(label);
    }
  }
  rows.forEach((r, i) => {
    const xCenter = margin.left + i * slotW + slotW / 2;
    const labelX = xCenter + slotW * (r.noLabelOffset ? 0 : (opts.xLabelOffsetRatio || 0));
    const rawHeight = (chartValue(r) / yScaleMax) * plotH;
    const h = rawHeight > 0 ? rawHeight : 0;
    const y = margin.top + plotH - h;
    const x = xCenter - barW / 2;
    svg.appendChild(mk('rect', { x, y, width: barW, height: h, fill: opts.color || '#1d4ed8', rx: 3, ry: 3 }));

    if (opts.showPct !== false && (rawHeight > 0 || opts.alwaysShowPct)) {
      const pctY = rawHeight > 0
        ? Math.max(margin.top + 10, y - 6)
        : margin.top + plotH - 6;
      const pctText = mk('text', { x: xCenter, y: pctY, 'text-anchor': 'middle', 'font-size': 9, fill: '#0f172a' });
      pctText.textContent = fmtPct(r.percent);
      svg.appendChild(pctText);
    }

    if (opts.showAllLabels || !isRangeColumn || i === 0 || i === rows.length - 1 || i % labelStep === 0) {
      const raw = axisLabel(r.label ?? '');
      const isOtherLabel = raw.startsWith('Other (') && raw.endsWith(')');
      if (isOtherLabel) {
        const t = mk('text', { class: 'axis-edge-label', x: labelX, y: margin.top + plotH + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' });
        const t1 = mk('tspan', { x: labelX, dy: 0 });
        t1.textContent = 'Other';
        t.appendChild(t1);
        const t2 = mk('tspan', { x: labelX, dy: 11 });
        t2.textContent = raw.replace('Other ', '');
        t.appendChild(t2);
        svg.appendChild(t);
      } else {
        const label = mk('text', { class: 'axis-edge-label', x: labelX, y: margin.top + plotH + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' });
        label.textContent = opts.noTruncateLabels ? raw : shortText(raw, 14);
        svg.appendChild(label);
      }
    }
  });
}

function drawStackedBars(svg, rows, opts = {}) {
  if (!svg) return;
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  const W = opts.w || 1080;
  const H = opts.h || 320;
  const margin = opts.margin || { top: 22, right: 24, bottom: 44, left: 72 };
  const plotW = W - margin.left - margin.right;
  const plotH = H - margin.top - margin.bottom;
  const rowPercent = (row) => {
    const value = Number(row.percent ?? 0);
    return Number.isFinite(value) ? value : 0;
  };
  const yScaleMax = opts.yScaleMax ?? opts.yMax ?? Math.max(1, ...rows.map(rowPercent)) * 1.12;
  const yTickMax = opts.yMax ?? yScaleMax;
  const slotW = plotW / Math.max(1, rows.length);
  const barW = Math.min(opts.maxBarWidth || 53, slotW * (opts.barRatio || 0.7));
  const exclusiveColor = opts.exclusiveColor || '#0f766e';
  const sharedColor = opts.sharedColor || '#d97706';

  svg.appendChild(mk('rect', { x: 0, y: 0, width: W, height: H, fill: '#fff' }));
  if (!rows.length) {
    const t = mk('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle', fill: '#64748b', 'font-size': 13 });
    t.textContent = 'No chart data for this page.';
    svg.appendChild(t);
    return;
  }

  for (let i = 0; i <= 5; i += 1) {
    const yv = yTickMax * (i / 5);
    const y = margin.top + plotH - (yv / yScaleMax) * plotH;
    svg.appendChild(mk('line', { x1: margin.left, y1: y, x2: W - margin.right, y2: y, stroke: '#e2e8f0' }));
    const yLabel = mk('text', { x: margin.left - 8, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' });
    yLabel.textContent = fmtPct(yv);
    svg.appendChild(yLabel);
  }
  svg.appendChild(mk('line', { x1: margin.left, y1: margin.top + plotH, x2: W - margin.right, y2: margin.top + plotH, stroke: '#475569' }));
  svg.appendChild(mk('line', { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotH, stroke: '#475569' }));

  rows.forEach((r, i) => {
    const exclusive = Number(r.exclusive_percent ?? r.exclusivePercent ?? r.exclusive ?? 0);
    const shared = Number(r.shared_percent ?? r.sharedPercent ?? r.shared ?? 0);
    const xCenter = margin.left + i * slotW + slotW / 2;
    const x = xCenter - barW / 2;
    const yBase = margin.top + plotH;
    const exclusiveH = (exclusive / yScaleMax) * plotH;
    const sharedH = (shared / yScaleMax) * plotH;

    svg.appendChild(mk('rect', { x, y: yBase - exclusiveH, width: barW, height: exclusiveH, fill: exclusiveColor, rx: 3, ry: 3 }));
    svg.appendChild(mk('rect', { x, y: yBase - exclusiveH - sharedH, width: barW, height: sharedH, fill: sharedColor, rx: 3, ry: 3 }));

    const valueLabel = mk('text', { x: xCenter, y: Math.max(margin.top + 10, yBase - exclusiveH - sharedH - 6), 'text-anchor': 'middle', 'font-size': 9, fill: '#0f172a' });
    valueLabel.textContent = fmtPct(r.percent);
    svg.appendChild(valueLabel);

    const label = mk('text', { class: 'axis-edge-label', x: xCenter, y: margin.top + plotH + 14, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' });
    label.textContent = opts.noTruncateLabels ? String(r.label ?? '') : shortText(r.label ?? '', 14);
    svg.appendChild(label);
  });
}

  Object.assign(D, {
    drawBars,
    drawStackedBars,
  });
})(window.Dashboard = window.Dashboard || {});
