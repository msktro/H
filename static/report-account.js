document.addEventListener("DOMContentLoaded", () => {
  const search = document.getElementById("report-target-search");
  const select = document.getElementById("report-target");
  const count = document.getElementById("report-target-count");
  if (!search || !select || !count) return;

  const placeholder = select.options[0].cloneNode(true);
  const allTargets = Array.from(select.options).slice(1).map(option => option.cloneNode(true));

  function filterTargets() {
    const query = search.value.trim().toLocaleLowerCase();
    const matches = allTargets.filter(option => option.textContent.toLocaleLowerCase().includes(query));
    const selected = select.value;
    select.replaceChildren(placeholder.cloneNode(true), ...matches);
    if (matches.some(option => option.value === selected)) select.value = selected;
    count.textContent = query ? `${matches.length}件見つかりました` : `全${matches.length}件から検索できます`;
  }

  search.addEventListener("input", filterTargets);
  filterTargets();
});
