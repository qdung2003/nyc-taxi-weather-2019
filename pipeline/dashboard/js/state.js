(function (D) {
  const rawData = window.DASHBOARD_DATA || {};

  function stepKeyFromIndex(index) {
    return String(index + 1).padStart(2, '0');
  }

  function maxColumnLength(fileData) {
    return Object.values(fileData || {}).reduce(
      (max, values) => (Array.isArray(values) ? Math.max(max, values.length) : max),
      0,
    );
  }

  function columnarToRows(fileData) {
    const headers = Object.keys(fileData || {});
    const rowCount = maxColumnLength(fileData);
    return Array.from({ length: rowCount }, (_, index) => (
      Object.fromEntries(headers.map((header) => [header, fileData[header]?.[index] ?? null]))
    ));
  }

  function metadataToObject(fileData) {
    const metadata = {};
    const keys = fileData?.key || [];
    const values = fileData?.value || [];
    keys.forEach((key, index) => {
      if (key !== null && key !== undefined && key !== '') metadata[String(key)] = values[index];
    });
    return metadata;
  }

  function withRowCount(fileData) {
    return { row_count: maxColumnLength(fileData), ...(fileData || {}) };
  }

  function groupRowsBy(rows, keyName) {
    const grouped = Object.create(null);
    rows.forEach((row) => {
      const key = row[keyName];
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(row);
    });
    return grouped;
  }

  function parseProfileStep(stepData) {
    const payload = { ...metadataToObject(stepData.metadata) };
    const lowColumns = columnarToRows(stepData.low_unique_columns);
    const lowValues = groupRowsBy(columnarToRows(stepData.low_unique_columns_array), 'column_name');
    lowColumns.forEach((column) => {
      const items = lowValues[column.column_name] || [];
      column.values = items.map((item) => item.value);
      column.counts = items.map((item) => item.count);
      column.percentages = items.map((item) => item.percentage);
    });

    const highColumns = [];
    const numericValues = groupRowsBy(columnarToRows(stepData.high_unique_columns_numeric_array), 'column_name');
    columnarToRows(stepData.high_unique_columns_numeric).forEach((column) => {
      const items = numericValues[column.column_name] || [];
      column.bin_edges = items.map((item) => item.bin_edge);
      column.bin_counts = items.map((item) => item.bin_count);
      column.bin_percentages = items.map((item) => item.bin_percentage);
      highColumns.push(column);
    });

    const datetimeValues = groupRowsBy(columnarToRows(stepData.high_unique_columns_datetime_array), 'column_name');
    columnarToRows(stepData.high_unique_columns_datetime).forEach((column) => {
      const items = (datetimeValues[column.column_name] || []).slice().sort((a, b) => Number(a.month || 0) - Number(b.month || 0));
      column.month_counts = items.map((item) => item.month_count);
      column.month_percentages = items.map((item) => item.month_percentage);
      highColumns.push(column);
    });

    highColumns.push(...columnarToRows(stepData.high_unique_columns));
    if (lowColumns.length) payload.low_unique_columns = lowColumns;
    if (highColumns.length) payload.high_unique_columns = highColumns;
    return payload;
  }

  function parseSchemaStep(stepData) {
    const filesRows = columnarToRows(stepData.files);
    return {
      ...metadataToObject(stepData.metadata),
      files: filesRows.map((row) => row.file ?? row.file_name).filter(Boolean),
      files_rows: filesRows,
      files_headers: Object.keys(stepData.files || {}),
      schema_rows: columnarToRows(stepData.schema),
      schema_headers: Object.keys(stepData.schema || {}),
      files_mismatches: [],
    };
  }

  function parsePaymentsStep(stepData) {
    const checks = columnarToRows(stepData.check_2_3);
    const groupedItems = groupRowsBy(columnarToRows(stepData.check_2_3_array), 'check');
    const check1 = columnarToRows(stepData.check_1)[0] || {};
    check1.columns = columnarToRows(stepData.check_1_array);
    return {
      checks: [
        check1,
        ...checks.map((row) => ({ ...row, columns: groupedItems[row.check] || [] })),
      ],
    };
  }

  function parseRulesStep(stepData) {
    return {
      ...metadataToObject(stepData.metadata),
      rules: columnarToRows(stepData.rules),
      rules_headers: Object.keys(stepData.rules || {}),
    };
  }

  function parseUpperBoundsStep(stepData) {
    const groupedBins = groupRowsBy(columnarToRows(stepData.column_bins_array), 'column_name');
    return {
      ...metadataToObject(stepData.metadata),
      columns: columnarToRows(stepData.column_bins).map((column) => {
        const items = groupedBins[column.column_name] || [];
        return {
          ...column,
          bin_edges: items.map((item) => item.bin_edge),
          bin_counts: items.map((item) => item.bin_count),
          bin_percentages: items.map((item) => item.bin_percentage),
        };
      }),
    };
  }

  function parseDailyWeatherMetricsStep(stepData) {
    const rows = columnarToRows(stepData.daily_weather_metrics);
    return { ...metadataToObject(stepData.metadata), rows, row_count: rows.length };
  }

  function parseWeatherImpactStep(stepData) {
    const impactSummary = withRowCount(stepData.impact_rain_summary);
    return {
      ...metadataToObject(stepData.metadata),
      rain_status: withRowCount(stepData.rain_status),
      rain_weekend: withRowCount(stepData.rain_weekend),
      rain_level: withRowCount(stepData.rain_level),
      avg_temp_level: withRowCount(stepData.avg_temp_level),
      temp_range_level: withRowCount(stepData.temp_range_level),
      impact_summary: impactSummary,
      weather_columns: ['prcp', 'avg_temp', 'temp_range'],
      metrics: impactSummary.metric || [],
    };
  }

  const STEP_PARSERS = {
    taxi: {
      '01': parseSchemaStep,
      '02': parseProfileStep,
      '03': parseProfileStep,
      '04': parsePaymentsStep,
      '05': parseRulesStep,
      '06': parseProfileStep,
      '07': parseUpperBoundsStep,
      '08': parseProfileStep,
    },
    weather: {
      '01': parseSchemaStep,
      '02': parseProfileStep,
      '03': parseProfileStep,
      '04': parseRulesStep,
      '05': parseProfileStep,
    },
    feature: {
      '01': parseProfileStep,
      '02': parseDailyWeatherMetricsStep,
      '03': parseWeatherImpactStep,
    },
  };

  function normalizeDomainData(domain) {
    const steps = Array.isArray(rawData[domain]) ? rawData[domain] : [];
    const parsers = STEP_PARSERS[domain] || {};
    return Object.fromEntries(steps.map((stepData, index) => {
      const stepKey = stepKeyFromIndex(index);
      const parser = parsers[stepKey] || ((value) => value);
      return [stepKey, { data: parser(stepData || {}) }];
    }));
  }

  const dashboardData = {
    taxi: normalizeDomainData('taxi'),
    weather: normalizeDomainData('weather'),
    feature: normalizeDomainData('feature'),
  };

  const getAvailableSteps = (domain) => Object.keys(dashboardData[domain] || {})
    .sort((a, b) => Number(a) - Number(b));
  const domains = ['taxi', 'weather', 'feature'].filter((domain) => getAvailableSteps(domain).length);
  let currentDomain = domains[0] || 'taxi';

  Object.assign(D, {
    dashboardData,
    domains,
    getAvailableSteps,
    getCurrentDomain: () => currentDomain,
    setCurrentDomain: (domain) => { currentDomain = domain; },
  });
})(window.Dashboard = window.Dashboard || {});
