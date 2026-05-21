(function (D) {
  const nav = document.getElementById('nav');
  const content = document.getElementById('content');
  if (!nav || !content) return;

  const {
    dashboardData,
    domains,
    getAvailableSteps,
    setCurrentDomain,
    getCurrentDomain,
    profileTemplate,
    rulesTemplate,
    STEP_TEMPLATES,
    STEP_RENDERERS,
    render05,
    renderFeature02,
    renderFeature03Combined,
    renderFeatureCategoryMetrics,
    renderFeature06,
    renderProfileTab,
    renderPrimitiveKpis,
  } = D;

  const stepRoot = content;
  nav.classList.add('nav-root');
  const stepCache = Object.fromEntries(domains.map((domain) => [domain, getAvailableSteps(domain)]));

  function getStepTemplate(domain, step) {
    if (domain === 'feature' && step === '01') return profileTemplate('EDA 01: profile features');
    if (domain === 'feature' && step === '02') return `
      <div class="card">
        <h1>EDA 02: daily weather metrics</h1>
        <div class="profile-top">
          <div class="kpis meta-common"></div>
          <div class="tabbar js-tabs"></div>
        </div>
      </div>
      <div class="card section">
        <div class="subhead" id="chartTitle">Daily metric</div>
        <svg id="chart" class="chart-frame" viewBox="0 0 1040 300" preserveAspectRatio="xMidYMid meet"></svg>
        <table class="feature02-table">
          <thead>
            <tr id="feature02Head">
              <th>date</th>
            </tr>
          </thead>
          <tbody id="feature02Body"></tbody>
        </table>
      </div>
    `;
    if (domain === 'feature' && step === '03') return `
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
      <div class="card section" id="rainStatusSection">
        <h2>Rain vs No Rain</h2>
        <div class="subhead" id="rainStatusTitle">Metric comparison</div>
        <svg id="rainStatusChart" class="chart-frame" viewBox="0 0 1040 300" preserveAspectRatio="xMidYMid meet"></svg>
        <table class="feature-category-table">
          <thead><tr id="rainStatusHead"></tr></thead>
          <tbody id="rainStatusBody"></tbody>
        </table>
      </div>
      <div class="card section" id="rainWeekendSection">
        <h2>Rain by Weekday/Weekend</h2>
        <div class="subhead" id="rainWeekendTitle">Metric comparison</div>
        <svg id="rainWeekendChart" class="chart-frame" viewBox="0 0 1040 300" preserveAspectRatio="xMidYMid meet"></svg>
        <table class="feature-category-table">
          <thead><tr id="rainWeekendHead"></tr></thead>
          <tbody id="rainWeekendBody"></tbody>
        </table>
      </div>
      <div class="card section" id="weatherLevelSection">
        <h2 id="weatherLevelHeading">Rain Levels</h2>
        <div class="subhead" id="rainLevelTitle">Metric comparison</div>
        <svg id="rainLevelChart" class="chart-frame" viewBox="0 0 1040 300" preserveAspectRatio="xMidYMid meet"></svg>
        <table class="feature-category-table">
          <thead><tr id="rainLevelHead"></tr></thead>
          <tbody id="rainLevelBody"></tbody>
        </table>
      </div>
      <div class="card section" id="feature03SummarySection">
        <h2>Impact Summary</h2>
        <table class="feature-summary-table">
          <thead>
            <tr>
              <th>metric</th>
              <th>rain_pct</th>
              <th>weekday_rain_pct</th>
              <th>weekend_rain_pct</th>
              <th>light_rain_pct</th>
              <th>medium_rain_pct</th>
              <th>heavy_rain_pct</th>
            </tr>
          </thead>
          <tbody id="feature03SummaryBody"></tbody>
        </table>
      </div>
    `;
    if (domain === 'feature' && step === '06') return `
      <div class="card">
        <h1>Feature EDA 06: weather impact summary</h1>
        <div class="profile-top">
          <div class="kpis meta-common"></div>
        </div>
      </div>
      <div class="card section">
        <div class="subhead">Percent difference from baseline</div>
        <table class="feature-summary-table">
          <thead>
            <tr>
              <th>metric</th>
              <th>rain_pct</th>
              <th>weekday_rain_pct</th>
              <th>weekend_rain_pct</th>
              <th>light_rain_pct</th>
              <th>medium_rain_pct</th>
              <th>heavy_rain_pct</th>
            </tr>
          </thead>
          <tbody id="feature06Body"></tbody>
        </table>
      </div>
    `;
    if (domain === 'weather' && step === '04') return rulesTemplate('EDA 04: before business rules');
    if (domain === 'weather' && step === '05') return profileTemplate('EDA 05: after business rules');
    return STEP_TEMPLATES[step] || '';
  }

  function getStepRenderer(domain, step) {
    if (domain === 'feature' && step === '01') return (root, data) => renderProfileTab(root, data, '06');
    if (domain === 'feature' && step === '02') return renderFeature02;
    if (domain === 'feature' && step === '03') return renderFeature03Combined;
    if (domain === 'feature' && step === '04') return (root, data) => renderFeatureCategoryMetrics(root, data, 'day_type_rain_status');
    if (domain === 'feature' && step === '05') return (root, data) => renderFeatureCategoryMetrics(root, data, 'rain_level');
    if (domain === 'feature' && step === '06') return renderFeature06;
    if (domain === 'weather' && step === '04') return render05;
    if (domain === 'weather' && step === '05') return (root, data) => renderProfileTab(root, data, '06');
    return STEP_RENDERERS[step];
  }

  function showStep(domain, step) {
    const stepsData = dashboardData[domain] || {};
    const availableSteps = stepCache[domain] || [];
    if (!availableSteps.includes(step)) return;
    if (typeof D.cleanupStep === 'function') {
      D.cleanupStep();
      D.cleanupStep = null;
    }
    setCurrentDomain(domain);

    nav.querySelectorAll('.nav-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.domain === domain && btn.dataset.step === step);
    });

    stepRoot.innerHTML = getStepTemplate(domain, step);
    const stepData = stepsData[step]?.data || {};
    const kpiStep = domain === 'feature' ? '02' : step;
    renderPrimitiveKpis(stepRoot, stepData, kpiStep);
    const renderer = getStepRenderer(domain, step);
    if (renderer) renderer(stepRoot, stepData);
  }

  nav.innerHTML = domains
    .map((domain) => {
      const steps = stepCache[domain] || [];
      return `
        <div class="nav-group nav-group-${domain}" aria-label="${domain} EDA steps">
          <span class="nav-label">${domain[0].toUpperCase()}${domain.slice(1)}</span>
          ${steps.map((s) => `<button class="nav-btn" data-domain="${domain}" data-step="${s}">${String(s).padStart(2, '0')}</button>`).join('')}
        </div>
      `;
    })
    .join('');
  nav.addEventListener('click', (e) => {
    const btn = e.target.closest('.nav-btn');
    if (!btn) return;
    showStep(btn.dataset.domain, btn.dataset.step);
  });

  showStep(getCurrentDomain(), (stepCache[getCurrentDomain()] || [])[0] || '01');
})(window.Dashboard = window.Dashboard || {});
