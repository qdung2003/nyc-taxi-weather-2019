(function (D) {
  const {
    mk,
    fmtPct,
    shortText,
    buildSideTicks,
    createChartPointY,
    createIndexedPointX,
    formatChartNumber,
    interpolateRatio,
  } = D;
  function resetSvg(svg, width, height) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.appendChild(mk('rect', { x: 0, y: 0, width, height, fill: '#fff' }));
  }

  function appendEmptyState(svg, width, height, text) {
    const label = mk('text', { x: width / 2, y: height / 2, 'text-anchor': 'middle', fill: '#64748b', 'font-size': 13 });
    label.textContent = text;
    svg.appendChild(label);
  }

  function drawAxes(svg, width, margin, plotHeight) {
    svg.appendChild(mk('line', { x1: margin.left, y1: margin.top + plotHeight, x2: width - margin.right, y2: margin.top + plotHeight, stroke: '#475569' }));
    svg.appendChild(mk('line', { x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + plotHeight, stroke: '#475569' }));
  }

  function drawYAxis(svg, width, margin, plotHeight, scaleMin, scaleMax, ticks, formatTick, options = {}) {
    const span = Math.max(1e-9, scaleMax - scaleMin);
    ticks.forEach((tick) => {
      if (options.skipTick?.(tick)) return;
      const y = margin.top + plotHeight - ((tick - scaleMin) / span) * plotHeight;
      svg.appendChild(mk('line', { x1: margin.left, y1: y, x2: width - margin.right, y2: y, stroke: '#e2e8f0' }));
      const label = mk('text', { x: margin.left - 8, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: '#64748b' });
      label.textContent = formatTick(tick);
      svg.appendChild(label);
    });
    drawAxes(svg, width, margin, plotHeight);
  }
function drawBars(svg, rows, opts = {}) {
  if (!svg) return;
  const W = opts.w || 1040;
  const H = opts.h || 252;
  resetSvg(svg, W, H);
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

  if (!rows.length) {
    appendEmptyState(svg, W, H, 'No chart data for this column.');
    return;
  }

  const firstTick = opts.hideZeroTick ? 1 : 0;
  drawYAxis(
    svg,
    W,
    margin,
    plotH,
    0,
    yScaleMax,
    Array.from({ length: 6 - firstTick }, (_, index) => yTickMax * ((index + firstTick) / 5)),
    fmtPct,
  );

  if (useLineChart) {
    const defaultPointX = createIndexedPointX(margin.left, plotW, rows.length);
    const pointX = (idx) => {
      if (splitRowsAtZero) {
        const value = numericValue(rows[idx]);
        if (value !== null) {
          const den = Math.max(1e-9, maxSplitValue - minSplitValue);
          return margin.left + ((value - minSplitValue) / den) * plotW;
        }
      }
      return defaultPointX(idx);
    };
    const pointY = createChartPointY(margin.top, plotH, 0, yScaleMax);
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
            const ratio = interpolateRatio(prev.value, point.value);
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
      const xZero = xForValue(0);
      const minGap = 44;
      const ticks = [
        ...buildSideTicks(minSplitValue, 0, xZero - margin.left, 90, 4),
        0,
        ...buildSideTicks(maxSplitValue, 0, W - margin.right - xZero, 90, 4).reverse(),
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
  const W = opts.w || 1080;
  const H = opts.h || 320;
  resetSvg(svg, W, H);
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

  if (!rows.length) {
    appendEmptyState(svg, W, H, 'No chart data for this page.');
    return;
  }

  drawYAxis(
    svg,
    W,
    margin,
    plotH,
    0,
    yScaleMax,
    Array.from({ length: 6 }, (_, index) => yTickMax * (index / 5)),
    fmtPct,
  );

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

function drawFeatureMetricLine(svg, rows, metric) {
  if (!svg) return;
  const W = 1040;
  const H = 300;
  resetSvg(svg, W, H);
  const margin = { top: 22, right: 24, bottom: 42, left: 86 };
  const plotW = W - margin.left - margin.right;
  const plotH = H - margin.top - margin.bottom;
  const values = rows.map((row) => Number(row[metric] ?? 0)).filter(Number.isFinite);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueSpan = Math.max(1e-9, maxValue - minValue);
  const splitAtZero = metric === 'avg_temp' && minValue < 0 && maxValue > 0;
  const yScaleMin = splitAtZero
    ? minValue - Math.abs(minValue) * 0.12
    : minValue < 0
      ? minValue - valueSpan * 0.18
      : Math.max(0, minValue - valueSpan * 0.18);
  const yScaleMax = splitAtZero
    ? maxValue + Math.abs(maxValue) * 0.12
    : maxValue + valueSpan * 0.18;
  const yScaleSpan = Math.max(1e-9, yScaleMax - yScaleMin);
  const pointX = createIndexedPointX(margin.left, plotW, rows.length);
  const pointY = createChartPointY(margin.top, plotH, yScaleMin, yScaleMax);
  if (!rows.length) {
    appendEmptyState(svg, W, H, 'No data.');
    return;
  }

  const yForTick = (value) => margin.top + plotH - ((value - yScaleMin) / yScaleSpan) * plotH;
  const yTicks = splitAtZero
    ? (() => {
        const yZero = yForTick(0);
        const minGap = 20;
        const ticks = [
          ...buildSideTicks(yScaleMin, 0, margin.top + plotH - yZero, 28, 6),
          0,
          ...buildSideTicks(yScaleMax, 0, yZero - margin.top, 28, 6).reverse(),
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
  drawYAxis(
    svg,
    W,
    margin,
    plotH,
    yScaleMin,
    yScaleMax,
    yTicks,
    formatChartNumber,
    { skipTick: (tick) => splitAtZero && Math.abs(tick) < 1e-12 },
  );

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
        const ratio = interpolateRatio(prevValue, value);
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

function drawFeatureCategoryBars(svg, rows, metric) {
  if (!svg) return;
  const W = 1040;
  const H = 300;
  resetSvg(svg, W, H);
  const margin = { top: 22, right: 24, bottom: 54, left: 92 };
  const plotW = W - margin.left - margin.right;
  const plotH = H - margin.top - margin.bottom;
  const values = rows.map((row) => Number(row[metric] ?? 0)).filter(Number.isFinite);
  const maxY = Math.max(1, ...values) * 1.12;
  const slotW = plotW / Math.max(1, rows.length);
  const barW = Math.min(96, slotW * 0.58);
  if (!rows.length) return;

  drawYAxis(
    svg,
    W,
    margin,
    plotH,
    0,
    maxY,
    Array.from({ length: 6 }, (_, index) => maxY * (index / 5)),
    formatChartNumber,
  );

  rows.forEach((row, index) => {
    const value = Number(row[metric] ?? 0);
    const xCenter = margin.left + index * slotW + slotW / 2;
    const height = (value / maxY) * plotH;
    const y = margin.top + plotH - height;
    const x = xCenter - barW / 2;
    svg.appendChild(mk('rect', { x, y, width: barW, height, fill: row.rain_status === 'rain' ? '#1d4ed8' : '#0f766e', rx: 3, ry: 3 }));
    const valueLabel = mk('text', { x: xCenter, y: Math.max(margin.top + 10, y - 6), 'text-anchor': 'middle', 'font-size': 10, fill: '#0f172a' });
    valueLabel.textContent = formatChartNumber(value);
    svg.appendChild(valueLabel);
    const label = mk('text', { x: xCenter, y: margin.top + plotH + 16, 'text-anchor': 'middle', 'font-size': 10, fill: '#475569' });
    label.textContent = row.label;
    svg.appendChild(label);
  });
}

  Object.assign(D, {
    drawBars,
    drawStackedBars,
    drawFeatureMetricLine,
    drawFeatureCategoryBars,
  });
})(window.Dashboard = window.Dashboard || {});
