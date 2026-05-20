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
    renderProfileTab,
    renderPrimitiveKpis,
  } = D;

  const stepRoot = content;
  nav.classList.add('nav-root');
  const stepCache = Object.fromEntries(domains.map((domain) => [domain, getAvailableSteps(domain)]));

  function getStepTemplate(domain, step) {
    if (domain === 'weather' && step === '04') return rulesTemplate('EDA 04: before business rules');
    if (domain === 'weather' && step === '05') return profileTemplate('EDA 05: after business rules');
    return STEP_TEMPLATES[step] || '';
  }

  function getStepRenderer(domain, step) {
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
    renderPrimitiveKpis(stepRoot, stepData, step);
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
