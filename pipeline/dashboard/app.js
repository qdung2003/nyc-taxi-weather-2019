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
    feature02Template,
    feature03Template,
    STEP_TEMPLATES,
    STEP_RENDERERS,
    render04,
    render05,
    render07,
    renderFeature02,
    renderFeature03Combined,
    renderProfileTab,
    renderPrimitiveKpis,
  } = D;

  const stepRoot = content;
  nav.classList.add('nav-root');
  const stepCache = Object.fromEntries(domains.map((domain) => [domain, getAvailableSteps(domain)]));
  const SPECIAL_STEPS = {
    'taxi:04': {
      template: () => STEP_TEMPLATES['04'] || '',
      renderer: render04,
    },
    'taxi:05': {
      template: () => profileTemplate('EDA 05: aggregate columns'),
      renderer: (root, data) => renderProfileTab(root, data, '03'),
      kpiStep: '05',
    },
    'taxi:06': {
      template: () => rulesTemplate('EDA 06: before business rules'),
      renderer: render05,
      kpiStep: '05',
    },
    'taxi:07': {
      template: () => profileTemplate('EDA 07: after business rules'),
      renderer: (root, data) => renderProfileTab(root, data, '06'),
      kpiStep: '06',
    },
    'taxi:08': {
      template: () => `
        <div class="card">
          <h1>EDA 08: before upper bounds</h1>
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
      renderer: render07,
      kpiStep: '07',
    },
    'taxi:09': {
      template: () => profileTemplate('EDA 09: after upper bounds'),
      renderer: (root, data) => renderProfileTab(root, data, '08'),
      kpiStep: '09',
    },
    'feature:01': {
      template: () => profileTemplate('EDA 01: profile features'),
      renderer: (root, data) => renderProfileTab(root, data, '06'),
    },
    'feature:02': {
      template: feature02Template,
      renderer: renderFeature02,
    },
    'feature:03': {
      template: feature03Template,
      renderer: renderFeature03Combined,
    },
    'weather:04': {
      template: () => rulesTemplate('EDA 04: before business rules'),
      renderer: render05,
      kpiStep: '05',
    },
    'weather:05': {
      template: () => profileTemplate('EDA 05: after business rules'),
      renderer: (root, data) => renderProfileTab(root, data, '06'),
      kpiStep: '06',
    },
  };

  function getStepTemplate(domain, step) {
    const special = SPECIAL_STEPS[`${domain}:${step}`];
    if (special?.template) return special.template();
    return STEP_TEMPLATES[step] || '';
  }

  function getStepRenderer(domain, step) {
    return SPECIAL_STEPS[`${domain}:${step}`]?.renderer || STEP_RENDERERS[step];
  }

  function getKpiStep(domain, step) {
    if (domain === 'feature') return '02';
    return SPECIAL_STEPS[`${domain}:${step}`]?.kpiStep || step;
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
    const kpiStep = getKpiStep(domain, step);
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
