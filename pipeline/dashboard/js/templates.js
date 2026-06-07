(function (D) {
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
    <div class="card section">
      <h2>Check 1</h2>
      <div class="muted" id="check1Desc"></div>
      <svg id="chart1" class="chart-frame" viewBox="0 0 1080 320" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead><tr><th>Condition</th><th>Rows tip = 0</th><th>Total rows by payment_type</th><th>Percent</th></tr></thead>
        <tbody id="tb1"></tbody>
      </table>
    </div>
    <div class="card section">
      <h2>Check 2</h2>
      <div class="muted" id="check2Desc"></div>
      <div class="small check-row-count" id="check2RowCount"></div>
      <svg id="chart2" class="chart-frame" viewBox="0 0 1080 320" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead><tr><th>Column</th><th>Rows (payment_type = 3 &amp; column = 0)</th><th>Percent</th></tr></thead>
        <tbody id="tb2"></tbody>
      </table>
    </div>
    <div class="card section">
      <h2>Check 3</h2>
      <div class="muted" id="check3Desc"></div>
      <div class="small check-row-count" id="check3RowCount"></div>
      <svg id="chart3" class="chart-frame" viewBox="0 0 1080 320" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead><tr><th>Column</th><th>Rows (payment_type = 4 &amp; column = 0)</th><th>Percent</th></tr></thead>
        <tbody id="tb3"></tbody>
      </table>
    </div>
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
      <svg id="chart" class="chart-frame" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
      <table>
        <thead><tr><th>Range</th><th>Count</th><th>Percent</th></tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  `,
  '08': profileTemplate('EDA 08: after upper bounds'),
};


  Object.assign(D, {
    profileTemplate,
    rulesTemplate,
    STEP_TEMPLATES,
  });
})(window.Dashboard = window.Dashboard || {});
