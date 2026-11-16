(() => {
  const startDate = document.getElementById("start-date");
  const endDate = document.getElementById("end-date");
  if (!startDate || !endDate) return;
  const localISODate = (date) => {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  };
  const today = localISODate(new Date());
  startDate.min = today;
  function syncDateRange() {
    endDate.min = startDate.value || today;
    if (startDate.value) {
      const maximum = new Date(`${startDate.value}T00:00:00`);
      maximum.setDate(maximum.getDate() + 29);
      endDate.max = localISODate(maximum);
    } else {
      endDate.removeAttribute("max");
    }
    if (endDate.value && (endDate.value < endDate.min || (endDate.max && endDate.value > endDate.max))) {
      endDate.value = "";
    }
  }
  startDate.addEventListener("change", syncDateRange);
  syncDateRange();
})();
