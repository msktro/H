(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const select = document.getElementById("days");
    const wrapper = document.getElementById("custom-days-wrap");
    const input = document.getElementById("custom-days");
    if (!select || !wrapper || !input) return;

    function update() {
      const custom = select.value === "other";
      wrapper.hidden = !custom;
      input.required = custom;
      if (!custom) input.setCustomValidity("");
    }

    select.addEventListener("change", update);
    update();
  });
})();
