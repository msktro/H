(() => {
  const button = document.getElementById("global-back-button");
  const entryKey = "tabidea:scroll:";
  let entryId = history.state && history.state.tabideaScrollEntry;
  if (!entryId) {
    entryId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    try { history.replaceState({ ...(history.state || {}), tabideaScrollEntry: entryId }, "", location.href); } catch (_) {}
  }
  const scrollKey = `${entryKey}${entryId}`;
  const savePosition = () => {
    try { sessionStorage.setItem(scrollKey, JSON.stringify({ x: window.scrollX, y: window.scrollY })); } catch (_) {}
  };
  history.scrollRestoration = "manual";
  window.addEventListener("pagehide", savePosition);
  window.addEventListener("pageshow", () => {
    let saved;
    try { saved = JSON.parse(sessionStorage.getItem(scrollKey) || "null"); } catch (_) {}
    if (!saved || !Number.isFinite(saved.x) || !Number.isFinite(saved.y)) return;
    requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(saved.x, saved.y)));
    try { sessionStorage.removeItem(scrollKey); } catch (_) {}
  });
  if (!button) return;
  button.addEventListener("click", () => {
    let internalPreviousPage = false;
    try { internalPreviousPage = Boolean(document.referrer) && new URL(document.referrer).origin === location.origin; } catch (_) {}
    if (internalPreviousPage && history.length > 1) {
      history.back();
    } else {
      location.assign(button.dataset.fallbackUrl || "/");
    }
  });
})();
