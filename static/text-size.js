(() => {
  const key = "tabidea-text-size";
  const allowed = new Set(["1", "1.1", "1.2"]);
  const originals = new WeakMap();

  function scaleElement(element, scale) {
    if (!originals.has(element)) {
      originals.set(element, {
        computed: Number.parseFloat(getComputedStyle(element).fontSize) || 16,
        inline: element.style.fontSize,
      });
    }
    const original = originals.get(element);
    element.style.fontSize = scale === 1 ? original.inline : `${original.computed * scale}px`;
  }

  function applySize(value) {
    const size = allowed.has(value) ? value : "1";
    const scale = Number(size);
    document.querySelectorAll("body *").forEach((element) => {
      const hasText = [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.nodeValue.trim());
      if (hasText || ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(element.tagName)) scaleElement(element, scale);
    });
    const selector = document.getElementById("text-size-selector");
    if (selector && selector.value !== size) selector.value = size;
    try { localStorage.setItem(key, size); } catch (_) { /* Storage may be disabled. */ }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const selector = document.getElementById("text-size-selector");
    let saved = "1";
    try { saved = localStorage.getItem(key) || "1"; } catch (_) { /* Use the default size. */ }
    applySize(saved);
    selector?.addEventListener("change", () => applySize(selector.value));
  });
})();
