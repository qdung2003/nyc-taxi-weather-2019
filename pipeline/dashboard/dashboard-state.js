(function (D) {
  const rawData = window.DASHBOARD_DATA || [];
  const dashboardData = Array.isArray(rawData)
    ? { taxi: Object.fromEntries(rawData.map((item, i) => [String(i + 1).padStart(2, '0'), { data: item }])) }
    : ((rawData && (rawData.taxi || rawData.weather))
      ? rawData
      : { taxi: ((rawData && rawData.steps) || {}) });
  const getAvailableSteps = (domain) => Object.keys(dashboardData[domain] || {})
    .filter((s) => /^\d+$/.test(String(s)))
    .sort((a, b) => Number(a) - Number(b));
  const domains = ['taxi', 'weather'].filter((domain) => getAvailableSteps(domain).length);
  let currentDomain = domains[0] || 'taxi';

  Object.assign(D, {
    dashboardData,
    domains,
    getAvailableSteps,
    getCurrentDomain: () => currentDomain,
    setCurrentDomain: (domain) => { currentDomain = domain; },
  });
})(window.Dashboard = window.Dashboard || {});
