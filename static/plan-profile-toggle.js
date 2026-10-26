(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("ai-plan-form");
    const toggle = document.getElementById("use-profile");
    const panel = document.getElementById("manual-preferences");
    const budget = document.getElementById("budget");
    const people = document.getElementById("people");
    const companionsField = document.getElementById("companions-field");
    if (!form || !toggle || !panel) return;

    const fields = ["manual-pace", "manual-transport", "manual-food", "manual-age-group"]
      .map((id) => document.getElementById(id)).filter(Boolean);
    const preferences = document.getElementById("preferences");
    const themeBoxes = [...panel.querySelectorAll("input[name='manual_themes']")];
    const themeError = document.getElementById("manual-theme-error");

    function sync() {
      const manual = !toggle.checked;
      if (people && companionsField) {
        companionsField.hidden = Number(people.value) <= 1;
        if (companionsField.hidden) {
          const companionInput = document.getElementById("companions");
          if (companionInput) companionInput.value = "";
        }
      }
      panel.hidden = !manual;
      fields.forEach((field) => { field.required = manual; });
      if (preferences) preferences.required = manual;
      if (budget) {
        budget.required = true;
        if (manual && toggle.dataset.wasChecked === "true") budget.value = "";
      }
      toggle.dataset.wasChecked = String(toggle.checked);
    }

    toggle.addEventListener("change", sync);
    people?.addEventListener("input", sync);
    people?.addEventListener("change", sync);
    sync();
    form.addEventListener("submit", (event) => {
      if (!toggle.checked && !themeBoxes.some((box) => box.checked)) {
        event.preventDefault();
        if (themeError) themeError.textContent = "テーマを1つ以上選んでください。";
        themeBoxes[0]?.focus();
        return;
      }
      if (themeError) themeError.textContent = "";
    });
    themeBoxes.forEach((box) => box.addEventListener("change", () => {
      if (themeBoxes.some((item) => item.checked) && themeError) themeError.textContent = "";
    }));
  });
})();
