(() => {
  const tabs = [...document.querySelectorAll("[data-group-tab]")];
  const panels = [...document.querySelectorAll("[data-group-panel]")];
  if (!tabs.length || !panels.length) return;

  function activate(name, updateHash = true) {
    const selected = tabs.find((tab) => tab.dataset.groupTab === name) || tabs[0];
    tabs.forEach((tab) => {
      const active = tab === selected;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.groupPanel !== selected.dataset.groupTab;
    });
    if (updateHash) history.replaceState(null, "", `#${selected.dataset.groupTab}`);
    document.dispatchEvent(new CustomEvent("group:tab-shown", { detail: selected.dataset.groupTab }));
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tab.dataset.groupTab));
    tab.addEventListener("keydown", (event) => {
      let next = index;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = tabs.length - 1;
      else return;
      event.preventDefault();
      tabs[next].focus();
      activate(tabs[next].dataset.groupTab);
    });
  });

  window.addEventListener("hashchange", () => activate(location.hash.slice(1), false));
  activate(location.hash.slice(1) || "overview", false);
})();
