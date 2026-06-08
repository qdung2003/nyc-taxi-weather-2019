(function (D) {
  function chartSvg(id, viewBox) {
    return `<svg id="${id}" class="chart-frame" viewBox="${viewBox}" preserveAspectRatio="xMidYMid meet"></svg>`;
  }

  function tableBlock(tableClass, headHtml, bodyId) {
    const classAttr = tableClass ? ` class="${tableClass}"` : '';
    return `
        <table${classAttr}>
          <thead>${headHtml}</thead>
          <tbody id="${bodyId}"></tbody>
        </table>
    `;
  }

  function featureCategorySection(sectionId, heading, titleId, chartId, headId, bodyId) {
    return `
      <div class="card section" id="${sectionId}">
        <h2>${heading}</h2>
        <div class="subhead" id="${titleId}">Metric comparison</div>
        ${chartSvg(chartId, '0 0 1040 300')}
        ${tableBlock('feature-category-table', `<tr id="${headId}"></tr>`, bodyId)}
      </div>
    `;
  }

  function paymentCheckSection(index, descriptionId, chartId, bodyId, headHtml, rowCountId = '') {
    const rowCount = rowCountId ? `<div class="small check-row-count" id="${rowCountId}"></div>` : '';
    return `
      <div class="card section">
        <h2>Check ${index}</h2>
        <div class="muted" id="${descriptionId}"></div>
        ${rowCount}
        ${chartSvg(chartId, '0 0 1080 320')}
        ${tableBlock('', headHtml, bodyId)}
      </div>
    `;
  }

  function profileTemplate(title) {
    return `
      <div class="card">
        <h1>${title}</h1>
        <div class="profile-top">
          <div class="kpis meta-common"></div>
          <div class="tabbar js-tabs"></div>
        </div>
      </div>
      <div class="card section">
        <div class="subhead">Column Snapshot</div>
        <div class="chips" id="chips"></div>
        <div class="subhead" id="chartTitle">Distribution</div>
        <svg id="chart" class="chart-frame" viewBox="0 0 1040 252" preserveAspectRatio="xMidYMid meet"></svg>
        <table>
          <thead><tr><th id="valueHeader">Value</th><th>Count</th><th>Percent</th></tr></thead>
          <tbody id="bodyRows"></tbody>
        </table>
      </div>
      <div class="card section profile-filter-card hidden">
        <div class="kpis meta-common profile-filter"></div>
      </div>
    `;
  }

  function rulesTemplate(title) {
    return `
      <div class="card">
        <h1>${title}</h1>
        <div class="eda01-top eda05-top">
          <div class="kpis meta-common"></div>
        </div>
      </div>
      <div class="card section eda05-rules-section">
        <div class="toolbar">
          <div class="eda05-chart-copy">
            <strong>Rules Chart (paged)</strong>
            <div class="small">Stacked bars per rule: Exclusive + Shared removed rows</div>
            <div class="small" id="pageInfo"></div>
          </div>
          <div class="btns">
            <button id="prevBtn">Prev</button>
            <button id="nextBtn">Next</button>
          </div>
        </div>
        <svg id="chart" class="chart-frame" viewBox="0 0 1080 320" preserveAspectRatio="xMidYMid meet"></svg>
        <div class="legend">
          <div><span class="dot" style="background:#0f766e;"></span>exclusive_removed_count</div>
          <div><span class="dot" style="background:#d97706;"></span>shared_removed_count</div>
        </div>
        <table class="eda05-rules-table">
          <thead><tr id="rulesHead"></tr></thead>
          <tbody id="rulesBody"></tbody>
        </table>
      </div>
    `;
  }

  function feature02Template() {
    return `
      <div class="card">
        <h1>EDA 02: daily weather metrics</h1>
        <div class="profile-top">
          <div class="kpis meta-common"></div>
          <div class="tabbar js-tabs"></div>
        </div>
      </div>
      <div class="card section">
        <div class="subhead" id="chartTitle">Daily metric</div>
        ${chartSvg('chart', '0 0 1040 300')}
        ${tableBlock('feature02-table', `
          <tr id="feature02Head">
            <th>date</th>
          </tr>
        `, 'feature02Body')}
      </div>
    `;
  }

  function feature03Template() {
    return `
      <div class="card">
        <h1>EDA 03: weather impact metrics</h1>
        <div class="profile-top">
          <div class="kpis meta-common"></div>
        </div>
        <div class="feature03-control-row">
          <div class="subhead">Select weather column:</div>
          <div class="tabbar" id="feature03WeatherTabs"></div>
        </div>
        <div class="feature03-control-row">
          <div class="subhead">Select taxi metric:</div>
          <div class="tabbar" id="feature03MetricTabs"></div>
        </div>
      </div>
      ${featureCategorySection('rainStatusSection', 'Rain vs No Rain', 'rainStatusTitle', 'rainStatusChart', 'rainStatusHead', 'rainStatusBody')}
      ${featureCategorySection('rainWeekendSection', 'Rain by Weekday/Weekend', 'rainWeekendTitle', 'rainWeekendChart', 'rainWeekendHead', 'rainWeekendBody')}
      <div class="card section" id="weatherLevelSection">
        <h2 id="weatherLevelHeading">Rain Levels</h2>
        <div class="subhead" id="rainLevelTitle">Metric comparison</div>
        ${chartSvg('rainLevelChart', '0 0 1040 300')}
        ${tableBlock('feature-category-table', '<tr id="rainLevelHead"></tr>', 'rainLevelBody')}
      </div>
      <div class="card section" id="feature03SummarySection">
        <h2>Impact Summary</h2>
        ${tableBlock('feature-summary-table', `
          <tr>
            <th>metric</th>
            <th>rain_pct</th>
            <th>weekday_rain_pct</th>
            <th>weekend_rain_pct</th>
            <th>light_rain_pct</th>
            <th>medium_rain_pct</th>
            <th>heavy_rain_pct</th>
          </tr>
        `, 'feature03SummaryBody')}
      </div>
    `;
  }

  const STEP_TEMPLATES = {
    '01': `
      <div class="card">
        <h1>EDA 01: schemas</h1>
        <div class="eda01-top">
          <div class="kpis meta-common"></div>
          <div class="eda01-files">
            <button id="k01FilesToggle" class="k01-files-toggle" type="button"></button>
            <div id="k01FilesList" class="hidden k01-files-list">
              <table class="files-table file-list-table">
                <thead id="k01FilesHead"></thead>
                <tbody id="k01FilesBody"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
      <div class="card section">
        <h2>Schema Compare</h2>
        <table class="files-table schema-table">
          <thead><tr id="k01SchemaHead"></tr></thead>
          <tbody id="k01SchemaBody"></tbody>
        </table>
      </div>
      <div class="card section">
        <h2>File List</h2>
        <table>
          <thead><tr><th>File</th><th>Mismatches</th></tr></thead>
          <tbody id="k01MismatchBody"></tbody>
        </table>
      </div>
    `,
    '02': profileTemplate('EDA 02: low duplicates'),
    '03': profileTemplate('EDA 03: high duplicates'),
    '04': `
      <div class="card">
        <h1>EDA 04: payments</h1>
      </div>
      ${paymentCheckSection('1', 'check1Desc', 'chart1', 'tb1', '<tr><th>Condition</th><th>Rows tip = 0</th><th>Total rows by payment_type</th><th>Percent</th></tr>')}
      ${paymentCheckSection('2', 'check2Desc', 'chart2', 'tb2', '<tr><th>Column</th><th>Rows (payment_type = 3 &amp; column = 0)</th><th>Percent</th></tr>', 'check2RowCount')}
      ${paymentCheckSection('3', 'check3Desc', 'chart3', 'tb3', '<tr><th>Column</th><th>Rows (payment_type = 4 &amp; column = 0)</th><th>Percent</th></tr>', 'check3RowCount')}
    `,
    '05': rulesTemplate('EDA 05: before business rules'),
    '06': profileTemplate('EDA 06: after business rules'),
    '07': `
      <div class="card">
        <h1>EDA 07: before upper bounds</h1>
        <div class="eda01-top">
          <div class="kpis meta-common"></div>
        </div>
      </div>
      <div class="card section">
        <div class="subhead">Column Snapshot</div>
        <div class="chips" id="chips"></div>
        <div id="tabs" class="tabs js-tabs"></div>
        <div class="subhead">Distribution</div>
        ${chartSvg('chart', '0 0 1000 280')}
        ${tableBlock('', '<tr><th>Range</th><th>Count</th><th>Percent</th></tr>', 'tbody')}
      </div>
    `,
    '08': profileTemplate('EDA 08: after upper bounds'),
  };


    Object.assign(D, {
      profileTemplate,
      rulesTemplate,
      feature02Template,
      feature03Template,
      STEP_TEMPLATES,
    });
  })(window.Dashboard = window.Dashboard || {});
