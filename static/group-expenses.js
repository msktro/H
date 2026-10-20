(() => {
  const toggle = document.getElementById("expense-delete-toggle");
  const list = document.getElementById("group-expense-list");
  const actions = document.getElementById("expense-bulk-actions");
  const form = document.getElementById("group-expense-bulk-form");
  const submit = document.getElementById("expense-bulk-submit");
  const count = document.getElementById("expense-selected-count");
  const cancel = document.getElementById("expense-delete-cancel");
  if (!toggle || !list || !actions || !form) return;

  const checkboxes = [...form.querySelectorAll('input[name="expense_ids"]')];
  function updateCount() {
    const selected = checkboxes.filter((checkbox) => checkbox.checked).length;
    count.textContent = `${selected}件選択中`;
    submit.disabled = selected === 0;
  }

  function setDeleteMode(enabled) {
    list.classList.toggle("is-delete-mode", enabled);
    actions.hidden = !enabled;
    toggle.setAttribute("aria-pressed", String(enabled));
    toggle.textContent = enabled ? "削除をやめる" : "削除";
    if (!enabled) checkboxes.forEach((checkbox) => { checkbox.checked = false; });
    updateCount();
  }

  toggle.addEventListener("click", () => {
    setDeleteMode(toggle.getAttribute("aria-pressed") !== "true");
  });
  cancel.addEventListener("click", () => setDeleteMode(false));
  checkboxes.forEach((checkbox) => checkbox.addEventListener("change", updateCount));
  form.addEventListener("submit", (event) => {
    if (!checkboxes.some((checkbox) => checkbox.checked)) {
      event.preventDefault();
      return;
    }
    const selected = checkboxes.filter((checkbox) => checkbox.checked).length;
    if (!window.confirm(`チェックした費用 ${selected}件を削除しますか？この操作は取り消せません。`)) {
      event.preventDefault();
    }
  });
})();
