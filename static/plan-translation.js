(() => {
  const cache = new Map();
  const pending = new Set();
  const languageNames = {
    ja: "日本語", en: "English", ko: "한국어",
    "zh-CN": "简体中文", "zh-TW": "繁體中文", th: "ไทย",
  };
  const titleSuffixes = {
    ja: "の旅行プラン", en: " travel plan", ko: " 여행 계획",
    "zh-CN": "的旅行计划", "zh-TW": "的旅遊計畫", th: " แผนการเดินทาง",
  };
  const statusText = {
    en: ["Translating the plan…", "Could not translate the plan. Check the AI settings or connection."],
    ko: ["여행 계획을 번역하고 있습니다…", "계획을 번역하지 못했습니다. AI 설정이나 연결을 확인하세요."],
    "zh-CN": ["正在翻译旅行计划…", "无法翻译此计划。请检查 AI 设置或网络连接。"],
    "zh-TW": ["正在翻譯旅遊計畫…", "無法翻譯此計畫。請檢查 AI 設定或網路連線。"],
    th: ["กำลังแปลแผนการเดินทาง…", "แปลแผนไม่สำเร็จ โปรดตรวจสอบการตั้งค่า AI หรือการเชื่อมต่อ"],
  };
  const translatedTitle = (title, locale) => title.replace(/の旅行プラン$/, titleSuffixes[locale] || titleSuffixes.ja);

  document.addEventListener("DOMContentLoaded", () => {
    const status = document.getElementById("plan-translation-status");
    const source = document.getElementById("itinerary-source");
    const itinerary = document.getElementById("itinerary-content");
    const selector = document.getElementById("plan-id");
    const preview = document.getElementById("plan-preview-body");
    const title = document.getElementById("plan-preview-title");
    const templates = new Map(
      Array.from(document.querySelectorAll("#plan-preview-data template[data-plan-id]")).map((item) => [item.dataset.planId, item])
    );

    const showStatus = (text) => {
      if (status) status.textContent = text;
    };

    async function translatePlan(planId, url, csrf, locale, raw) {
      if (!planId || !url || !locale || locale === "ja") return raw;
      let fingerprint = 2166136261;
      for (let i = 0; i < raw.length; i += 1) fingerprint = Math.imul(fingerprint ^ raw.charCodeAt(i), 16777619);
      const key = `${planId}:${locale}:${(fingerprint >>> 0).toString(36)}`;
      if (cache.has(key)) return cache.get(key);
      try {
        const saved = sessionStorage.getItem(`tabidea-plan-translation:${key}`);
        if (saved) { cache.set(key, saved); return saved; }
      } catch (_) { /* Translation still works when browser storage is unavailable. */ }
      if (pending.has(key)) return null;
      pending.add(key);
      showStatus(statusText[locale]?.[0] || `プランを${languageNames[locale] || locale}に翻訳中です…`);
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify({ locale }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "翻訳できませんでした。");
        cache.set(key, result.text);
        try { sessionStorage.setItem(`tabidea-plan-translation:${key}`, result.text); } catch (_) { /* Optional session cache. */ }
        showStatus("");
        return result.text;
      } catch (error) {
        showStatus(statusText[locale]?.[1] || error.message || "プランを翻訳できませんでした。AIの設定や通信状態を確認してください。");
        return null;
      } finally {
        pending.delete(key);
      }
    }

    async function updatePlanLanguage(locale = document.documentElement.lang || "ja") {
      if (status && source && itinerary) {
        const raw = source.content.textContent.trim();
        if (locale === "ja") {
          document.dispatchEvent(new CustomEvent("tabidea:plan-translated", { detail: { text: raw } }));
          showStatus("");
        } else {
          const translated = await translatePlan(status.dataset.planId, status.dataset.translateUrl, status.dataset.csrf, locale, raw);
          if (translated !== null && document.documentElement.lang === locale) {
            document.dispatchEvent(new CustomEvent("tabidea:plan-translated", { detail: { text: translated } }));
          }
        }
      }

      if (selector && preview && title) {
        const selected = templates.get(selector.value);
        if (!selected) return;
        const raw = selected.content.textContent.trim();
        title.textContent = translatedTitle(selected.dataset.planTitle, locale);
        if (locale === "ja") {
          preview.textContent = raw;
          showStatus("");
        } else {
          const translated = await translatePlan(selected.dataset.planId, selected.dataset.translateUrl, selected.dataset.csrf, locale, raw);
          if (translated !== null && selector.value === selected.dataset.planId && document.documentElement.lang === locale) preview.textContent = translated;
        }
      }
    }

    document.addEventListener("tabidea:language-changed", (event) => updatePlanLanguage(event.detail?.locale));
    if (selector) selector.addEventListener("change", () => updatePlanLanguage());
    updatePlanLanguage();
  });
})();
