(function (D) {
  function buildSideTicks(start, end, availableSize, minSpacing, maxSegments) {
    const segmentCount = Math.max(1, Math.min(maxSegments, Math.floor(availableSize / minSpacing)));
    return Array.from({ length: segmentCount }, (_, index) => start + (end - start) * (index / segmentCount));
  }

  function formatChartNumber(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '';
    return numeric.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function interpolateRatio(fromValue, toValue, targetValue = 0) {
    return (targetValue - fromValue) / Math.max(1e-9, toValue - fromValue);
  }

  function createIndexedPointX(marginLeft, plotWidth, count) {
    const denominator = Math.max(1, count - 1);
    return (index) => marginLeft + (index / denominator) * plotWidth;
  }

  function createChartPointY(marginTop, plotHeight, minValue, maxValue) {
    const span = Math.max(1e-9, maxValue - minValue);
    return (value) => marginTop + plotHeight - ((Number(value || 0) - minValue) / span) * plotHeight;
  }

  Object.assign(D, {
    buildSideTicks,
    formatChartNumber,
    interpolateRatio,
    createIndexedPointX,
    createChartPointY,
  });
})(window.Dashboard = window.Dashboard || {});
