(() => {
  const startDate = document.getElementById("start-date");
  const endDate = document.getElementById("end-date");
  if (!startDate || !endDate) return;

  function syncDateRange() {
    endDate.min = startDate.value;
    if (startDate.value && endDate.value && endDate.value < startDate.value) {
      endDate.value = "";
    }
  }

  startDate.addEventListener("change", syncDateRange);
  syncDateRange();
})();
