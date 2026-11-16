document.addEventListener("DOMContentLoaded", () => {
  const count = document.getElementById("manual-days"), days = document.getElementById("manual-day-list");
  const dayTemplate = document.getElementById("manual-day-template"), stopTemplate = document.getElementById("manual-stop-template");
  let draft = {}; try { draft = JSON.parse(document.getElementById("manual-plan-draft")?.textContent || "{}"); } catch (_) {}
  if (!count || !days || !dayTemplate || !stopTemplate) return;
  const startDate = document.getElementById("manual-start-date");
  if (startDate) {
    const today = new Date();
    today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
    startDate.min = today.toISOString().slice(0, 10);
  }
  function addStop(n, item = {}) {
    const fragment = stopTemplate.content.cloneNode(true), row = fragment.querySelector(".manual-plan-stop");
    row.querySelector('[name="stop_day"]').value = n;
    row.querySelector('[name="stop_time"]').value = item.time || "";
    row.querySelector('[name="stop_name"]').value = item.name || "";
    row.querySelector('[name="stop_category"]').value = item.category || "観光・体験";
    row.querySelector('[name="stop_description"]').value = item.description || "";
    days.querySelector(`[data-day-number="${n}"] .manual-plan-stop-list`).append(fragment);
  }
  function addDay(n, title = "") {
    const fragment = dayTemplate.content.cloneNode(true), panel = fragment.querySelector(".manual-plan-day");
    panel.dataset.dayNumber = n;
    panel.querySelector(".manual-plan-day-heading").textContent = `旅行 ${n} 日目`;
    panel.querySelector('[name="day_title"]').value = title || `${n}日目の予定`;
    days.append(fragment); addStop(n);
  }
  function syncDays() {
    const wanted = Math.max(1, Math.min(30, Number(count.value) || 1)); count.value = wanted;
    while (days.children.length > wanted) days.lastElementChild.remove();
    while (days.children.length < wanted) addDay(days.children.length + 1);
    [...days.children].forEach((panel, i) => {
      const n = i + 1; panel.dataset.dayNumber = n;
      panel.querySelector(".manual-plan-day-heading").textContent = `旅行 ${n} 日目`;
      panel.querySelectorAll('[name="stop_day"]').forEach(input => input.value = n);
    });
  }
  count.addEventListener("input", syncDays);
  days.addEventListener("click", event => {
    const add = event.target.closest("[data-add-stop]");
    if (add) { addStop(Number(add.closest(".manual-plan-day").dataset.dayNumber)); return; }
    const remove = event.target.closest("[data-remove-stop]");
    if (remove) { const list = remove.closest(".manual-plan-stop-list"); if (list.children.length > 1) remove.closest(".manual-plan-stop").remove(); }
  });
  const titles = Array.isArray(draft.day_titles) ? draft.day_titles : [];
  const initialDays = Math.max(1, Math.min(30, Number(draft.days) || 1)); count.value = initialDays;
  for (let n = 1; n <= initialDays; n++) addDay(n, titles[n - 1]);
  (Array.isArray(draft.stops) ? draft.stops : []).forEach(item => {
    const n = Number(item.day); if (!n || n < 1 || n > initialDays) return;
    const first = days.querySelector(`[data-day-number="${n}"] .manual-plan-stop-list .manual-plan-stop`);
    if (first && !first.querySelector('[name="stop_name"]').value) first.remove();
    addStop(n, item);
  });
});
