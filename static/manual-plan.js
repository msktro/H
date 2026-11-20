document.addEventListener("DOMContentLoaded", () => {
  const days = document.getElementById("manual-day-list");
  const dayTemplate = document.getElementById("manual-day-template"), stopTemplate = document.getElementById("manual-stop-template");
  const startDate = document.getElementById("manual-start-date"), endDate = document.getElementById("manual-end-date");
  let draft = {}; try { draft = JSON.parse(document.getElementById("manual-plan-draft")?.textContent || "{}"); } catch (_) {}
  if (!days || !dayTemplate || !stopTemplate || !startDate || !endDate) return;
  const localISO = date => {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 10);
  };
  const today = localISO(new Date());
  const parkedDays = new Map();
  startDate.min = today;
  function addStop(n, item = {}) {
    const fragment = stopTemplate.content.cloneNode(true), row = fragment.querySelector(".manual-plan-stop");
    row.querySelector('[name="stop_day"]').value = n;
    row.querySelector('[name="stop_time"]').value = item.time || "";
    row.querySelector('[name="stop_name"]').value = item.name || "";
    row.querySelector('[name="stop_category"]').value = item.category || "観光・体験";
    row.querySelector('[name="stop_description"]').value = item.description || "";
    days.querySelector(`[data-day-number="${n}"] .manual-plan-stop-list`).append(fragment);
  }
  function makeDay(n, title = "") {
    const fragment = dayTemplate.content.cloneNode(true), panel = fragment.querySelector(".manual-plan-day");
    panel.dataset.dayNumber = n;
    panel.querySelector(".manual-plan-day-heading").textContent = `旅行 ${n} 日目`;
    panel.querySelector('[name="day_title"]').value = title || `${n}日目の予定`;
    days.append(fragment); addStop(n);
    return days.lastElementChild;
  }
  function resizeDays(wanted) {
    wanted = Math.max(1, Math.min(30, wanted));
    while (days.children.length > wanted) {
      const panel = days.lastElementChild;
      parkedDays.set(Number(panel.dataset.dayNumber), panel);
      panel.remove();
    }
    while (days.children.length < wanted) {
      const n = days.children.length + 1, parked = parkedDays.get(n);
      if (parked) { parkedDays.delete(n); days.append(parked); }
      else makeDay(n, (Array.isArray(draft.day_titles) ? draft.day_titles[n - 1] : "") || "");
    }
    [...days.children].forEach((panel, i) => {
      const n = i + 1; panel.dataset.dayNumber = n;
      panel.querySelector(".manual-plan-day-heading").textContent = `旅行 ${n} 日目`;
      panel.querySelectorAll('[name="stop_day"]').forEach(input => input.value = n);
    });
  }
  function syncDateRange() {
    endDate.min = startDate.value || today;
    if (startDate.value) {
      const maximum = new Date(`${startDate.value}T00:00:00`);
      maximum.setDate(maximum.getDate() + 29);
      endDate.max = localISO(maximum);
    } else endDate.removeAttribute("max");
    const valid = startDate.value && endDate.value && endDate.value >= startDate.value && (!endDate.max || endDate.value <= endDate.max);
    endDate.setCustomValidity(endDate.value && !valid ? "帰着日は出発日以降、出発日から30日以内にしてください。" : "");
    if (valid) {
      const [sy, sm, sd] = startDate.value.split("-").map(Number), [ey, em, ed] = endDate.value.split("-").map(Number);
      const duration = (Date.UTC(ey, em - 1, ed) - Date.UTC(sy, sm - 1, sd)) / 86400000 + 1;
      resizeDays(duration);
    }
  }
  const titles = Array.isArray(draft.day_titles) ? draft.day_titles : [];
  const initialDays = Math.max(1, Math.min(30, Number(draft.days) || titles.length || 1));
  for (let n = 1; n <= initialDays; n++) makeDay(n, titles[n - 1]);
  (Array.isArray(draft.stops) ? draft.stops : []).forEach(item => {
    const n = Number(item.day); if (!n || n < 1 || n > initialDays) return;
    const first = days.querySelector(`[data-day-number="${n}"] .manual-plan-stop-list .manual-plan-stop`);
    if (first && !first.querySelector('[name="stop_name"]').value) first.remove();
    addStop(n, item);
  });
  startDate.addEventListener("change", syncDateRange);
  endDate.addEventListener("change", syncDateRange);
  syncDateRange();
  days.addEventListener("click", event => {
    const add = event.target.closest("[data-add-stop]");
    if (add) { addStop(Number(add.closest(".manual-plan-day").dataset.dayNumber)); return; }
    const remove = event.target.closest("[data-remove-stop]");
    if (remove) { const list = remove.closest(".manual-plan-stop-list"); if (list.children.length > 1) remove.closest(".manual-plan-stop").remove(); }
  });
});
