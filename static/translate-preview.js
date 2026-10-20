(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const selector = document.getElementById("plan-id");
    const title = document.getElementById("plan-preview-title");
    const body = document.getElementById("plan-preview-body");
    const empty = document.getElementById("plan-preview-empty");
    const emptyText = {
      ja: ["旅行プランの表示", "旅行プランを選択してください。選択すると、ここにすぐ表示されます。"],
      en: ["Trip plan preview", "Select a travel plan to preview it here."],
      ko: ["여행 계획 미리보기", "여행 계획을 선택하면 여기에 바로 표시됩니다."],
      "zh-CN": ["旅行计划预览", "请选择旅行计划，内容会立即显示在这里。"],
      "zh-TW": ["旅遊計畫預覽", "請選擇旅遊計畫，內容會立即顯示於此。"],
      th: ["ตัวอย่างแผนการเดินทาง", "โปรดเลือกแผนการเดินทาง เนื้อหาจะแสดงที่นี่ทันที"],
    };
    const templates = new Map(
      Array.from(document.querySelectorAll("#plan-preview-data template[data-plan-id]"))
        .map((item) => [item.dataset.planId, item])
    );
    if (!selector || !title || !body || !empty) return;

    function showSelectedPlan() {
      const selected = templates.get(selector.value);
      if (!selected) {
        const locale = document.documentElement.lang || "ja";
        const words = emptyText[locale] || emptyText.ja;
        title.textContent = words[0];
        body.textContent = "";
        body.hidden = true;
        empty.hidden = false;
        empty.textContent = words[1];
        return;
      }
      title.textContent = selected.dataset.planTitle;
      body.textContent = selected.content.textContent.trim();
      body.hidden = false;
      empty.hidden = true;
    }

    selector.addEventListener("change", showSelectedPlan);
    document.addEventListener("tabidea:language-changed", showSelectedPlan);
    showSelectedPlan();
  });
})();
