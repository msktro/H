(() => {
  const selector = "[data-listing-id].review-translatable-name";
  const cacheKey = (locale, id) => `tabidea-review-name:${locale}:${id}`;

  async function translateNames(locale) {
    const elements = [...document.querySelectorAll(selector)];
    elements.forEach((element) => {
      if (element.dataset.originalName === undefined) element.dataset.originalName = element.textContent.trim();
      element.textContent = element.dataset.originalName;
    });
    if (locale === "ja" || !elements.length) return;

    const uncached = elements.filter((element) => !sessionStorage.getItem(cacheKey(locale, element.dataset.listingId)));
    if (uncached.length) {
      const csrf = document.querySelector("input[name='csrf_token']")?.value;
      if (!csrf) return;
      try {
        const response = await fetch("/api/reviews/translate-names", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify({ locale, ids: uncached.map((element) => Number(element.dataset.listingId)) }),
        });
        if (!response.ok) return;
        const result = await response.json();
        Object.entries(result.names || {}).forEach(([id, name]) => {
          if (name) sessionStorage.setItem(cacheKey(locale, id), name);
        });
      } catch (_) {
        return;
      }
    }
    if (document.documentElement.lang !== locale) return;
    elements.forEach((element) => {
      const translated = sessionStorage.getItem(cacheKey(locale, element.dataset.listingId));
      if (translated) element.textContent = translated;
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const initialLocale = document.documentElement.lang || "ja";
    translateNames(initialLocale);
    document.addEventListener("tabidea:language-changed", (event) => translateNames(event.detail.locale));
  });
})();
