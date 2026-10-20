(() => {
  const form = document.getElementById("ai-plan-form");
  const overlay = document.getElementById("ai-plan-loading");
  const submit = document.getElementById("ai-plan-submit");
  if (!form || !overlay) return;

  form.addEventListener("submit", (event) => {
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "true";
    overlay.classList.add("is-visible");
    overlay.setAttribute("aria-hidden", "false");
    submit?.setAttribute("aria-disabled", "true");
    if (submit) submit.textContent = "生成中…";
  });
})();
