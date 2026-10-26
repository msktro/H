(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-group-delete-form]");
    if (!form) return;

    form.addEventListener("submit", (event) => {
      const input = form.elements.namedItem("confirm_group_name");
      const expectedName = form.dataset.groupName || "";
      if (!input || input.value.trim() !== expectedName) {
        event.preventDefault();
        window.alert("入力したグループ名が一致しません。名前を確認してください。");
        input?.focus();
        return;
      }

      if (!window.confirm(`「${expectedName}」を削除します。メンバー、チャット、費用、旅程メモ、アルバムも削除されます。共有プラン自体は残ります。よろしいですか？`)) {
        event.preventDefault();
      }
    });
  });
})();
