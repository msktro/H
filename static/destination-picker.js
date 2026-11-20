(() => {
  const picker = document.getElementById('destination-picker');
  const hidden = document.getElementById('destination');
  const summary = document.getElementById('prefecture-summary');
  if (!picker || !hidden || !summary) return;
  const checks = [...picker.querySelectorAll('[data-prefecture]')];
  const emptyLabel = picker.dataset.emptyLabel || '未定（都道府県を選択）';
  const emptyValue = picker.dataset.emptyValue ?? '未定';
  const destinationError = picker.closest('form')?.querySelector('[data-destination-error]');
  document.addEventListener('click', event => {
    if (picker.open && !picker.contains(event.target)) picker.open = false;
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && picker.open) {
      picker.open = false;
      picker.querySelector('summary')?.focus();
    }
  });
  const regions = [...picker.querySelectorAll('[data-region]')];
  const search = document.getElementById('prefecture-search');
  const update = () => {
    const chosen = checks.filter(box => box.checked).map(box => box.value);
    hidden.value = chosen.length ? chosen.join('、') : emptyValue;
    summary.textContent = chosen.length ? chosen.join('、') : emptyLabel;
    if (destinationError && chosen.length) { destinationError.hidden = true; summary.removeAttribute('aria-invalid'); }
    checks.forEach(box => { box.disabled = !box.checked && chosen.length >= 8; });
    regions.forEach(region => {
      const items = [...region.querySelectorAll('[data-prefecture]')];
      const count = items.filter(box => box.checked).length;
      region.querySelector('[data-region-count]').textContent = count ? `${count}/${items.length}` : `${items.length}県`;
    });
  };
  checks.forEach(box => box.addEventListener('change', update));
  document.getElementById('prefecture-clear')?.addEventListener('click', () => {
    checks.forEach(box => { box.checked = false; }); update(); picker.open = false;
  });
  if (picker.dataset.required === 'true') {
    picker.closest('form')?.addEventListener('submit', event => {
      const hasDestination = checks.some(box => box.checked);
      if (hasDestination) return;
      event.preventDefault();
      if (destinationError) destinationError.hidden = false;
      summary.setAttribute('aria-invalid', 'true');
      summary.focus();
      picker.open = true;
    });
  }
  search?.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    regions.forEach(region => {
      const items = [...region.querySelectorAll('.prefecture-picker-option')];
      const visibleCount = items.reduce((count, label) => {
        const visible = !query || label.textContent.toLocaleLowerCase().includes(query);
        label.hidden = !visible;
        return count + Number(visible);
      }, 0);
      region.hidden = visibleCount === 0;
      if (query && visibleCount) region.open = true;
      if (!query) region.open = false;
    });
  });
  update();
})();
