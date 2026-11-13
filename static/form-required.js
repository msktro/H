(() => {
  const markRequired = (root = document) => {
    root.querySelectorAll('input[required], select[required], textarea[required]').forEach((field) => {
      const label = field.id ? root.querySelector(`label[for="${CSS.escape(field.id)}"]`) : field.closest('label');
      if (label && field.required && !label.querySelector('.required-mark')) {
        const badge = document.createElement('span');
        badge.className = 'required-mark'; badge.textContent = '必須';
        label.append(' ', badge);
      } else if (label && !field.required) {
        label.querySelector('.required-mark')?.remove();
      }
    });
    root.querySelectorAll('fieldset[data-required-group]').forEach((group) => {
      const boxes = [...group.querySelectorAll('input[type="checkbox"]:not(:disabled)')];
      if (!boxes.length) return;
      const inactive = Boolean(group.closest('[hidden]'));
      const selected = boxes.some((box) => box.checked);
      boxes[0].setCustomValidity(!inactive && !selected
        ? (group.dataset.validationMessage || '1つ以上選択してください。')
        : '');
      boxes.forEach((box) => {
        if (box.dataset.requiredGroupBound) return;
        box.dataset.requiredGroupBound = 'true';
        box.addEventListener('change', () => markRequired(document));
      });
    });
    root.querySelectorAll('input[data-match-field]').forEach((field) => {
      const other = document.getElementById(field.dataset.matchField);
      if (!other) return;
      field.setCustomValidity(field.value && other.value && field.value !== other.value
        ? (field.dataset.matchMessage || '入力内容が一致しません。')
        : '');
      if (field.dataset.matchBound) return;
      field.dataset.matchBound = 'true';
      const syncMatch = () => markRequired(document);
      field.addEventListener('input', syncMatch);
      other.addEventListener('input', syncMatch);
    });
    root.querySelectorAll('input[data-length-min], input[data-length-max]').forEach((field) => {
      const valueLength = Array.from(field.value.trim()).length;
      const min = Number(field.dataset.lengthMin || 0);
      const max = Number(field.dataset.lengthMax || Number.MAX_SAFE_INTEGER);
      const invalid = valueLength > 0 && (valueLength < min || valueLength > max);
      field.setCustomValidity(invalid ? (field.dataset.lengthMessage || '入力文字数を確認してください。') : '');
      if (field.dataset.lengthBound) return;
      field.dataset.lengthBound = 'true';
      field.addEventListener('input', () => markRequired(document));
    });
  };
  const isNewPlanForm = Boolean(document.getElementById('ai-plan-form'));
  // 旅行プラン作成フォームに残っている旧バージョンの入力値を引き継がない。
  const key = `tabidea-form:${isNewPlanForm ? 'v2:' : ''}${location.pathname}${location.search}`;
  const logoutLoginForm = document.querySelector('form[data-clear-login="true"]');
  if (logoutLoginForm) {
    const clearLoginFields = () => {
      logoutLoginForm.querySelectorAll('input:not([type="hidden"])').forEach((field) => { field.value = ''; });
      sessionStorage.removeItem(key);
    };
    clearLoginFields();
    window.addEventListener('pageshow', clearLoginFields);
    window.setTimeout(clearLoginFields, 100);
  }
  const noPersistForms = [...document.querySelectorAll('form[data-no-persist="true"]')];
  if (noPersistForms.length) sessionStorage.removeItem(key);
  const pendingClearKey = 'tabidea-form-clear-on-success';
  try {
    const pending = JSON.parse(sessionStorage.getItem(pendingClearKey) || 'null');
    if (pending && document.querySelector('.flash.success') && location.pathname !== pending.path) {
      sessionStorage.removeItem(pending.key);
      sessionStorage.removeItem(pendingClearKey);
    } else if (pending && location.pathname === pending.path) {
      // POST後に入力画面へ戻った場合は、成功遷移ではないため入力値を残す。
      sessionStorage.removeItem(pendingClearKey);
    }
  } catch (_) { sessionStorage.removeItem(pendingClearKey); }
  const restore = () => {
    if (document.querySelector('.flash.success')) { sessionStorage.removeItem(key); return; }
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
      if (!saved) return;
      document.querySelectorAll('form').forEach((form, index) => {
        if (form.dataset.noPersist === 'true') return;
        if (index !== saved.formIndex) return;
        for (const [name, values] of Object.entries(saved.values)) {
          const fields = [...form.querySelectorAll(`[name="${CSS.escape(name)}"]`)];
          fields.forEach((field, i) => {
            if (field.type === 'password' || field.type === 'file') return;
            if (field.type === 'checkbox' || field.type === 'radio') field.checked = values[i] === field.value;
            else field.value = values[i] ?? '';
          });
        }
      });
    } catch (_) { sessionStorage.removeItem(key); }
  };
  restore(); markRequired();
  document.querySelectorAll('input[data-report-validity="true"]').forEach((field) => {
    window.setTimeout(() => { field.focus({ preventScroll: false }); field.reportValidity(); }, 0);
  });
  document.querySelectorAll('form').forEach((form, formIndex) => form.addEventListener('submit', () => {
    if (form.dataset.noPersist === 'true') return;
    const values = {};
    form.querySelectorAll('[name]').forEach((field) => {
      if (field.type === 'password' || field.type === 'file' || field.name === 'csrf_token') return;
      (values[field.name] ||= []).push(field.type === 'checkbox' || field.type === 'radio' ? (field.checked ? field.value : '') : field.value);
    });
    sessionStorage.setItem(key, JSON.stringify({ formIndex, values }));
    if (form.dataset.clearOnSuccess === 'true') {
      sessionStorage.setItem(pendingClearKey, JSON.stringify({ key, path: location.pathname }));
    }
  }));
  new MutationObserver(() => markRequired()).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'required'] });
})();
