(() => {
  const source = document.querySelector("#itinerary-source");
  const root = document.querySelector("#itinerary-content");
  if (!source || !root) return;

  const clean = (text) => text.replace(/^\s{0,3}#{1,6}\s*/, "").replace(/\*\*(.*?)\*\*/g, "$1").replace(/__(.*?)__/g, "$1").replace(/`/g, "").trim();
  const dayMatch = (text) => {
    const match = text.match(/^(?:第\s*)?(\d+)\s*日目(?:\s*[｜|:：—-]\s*(.*))?$/i)
      || text.match(/^Day\s*(\d+)(?:\s*[｜|:：—-]\s*(.*))?$/i);
    return match ? { number: Number(match[1]), title: (match[2] || "").trim() } : null;
  };
  const isTimeSection = (text) => /^(午前|朝|昼|昼食|ランチ|午後|夕方|夜|夕食|移動|宿泊|朝食|morning|breakfast|lunch|afternoon|evening|night|transport|accommodation|오전|아침|점심|오후|저녁|이동|숙박|早餐|早上|上午|中午|午餐|下午|傍晚|晚上|交通|住宿|อาหารเช้า|เช้า|เที่ยง|บ่าย|เย็น|ค่ำ|การเดินทาง|ที่พัก)/i.test(text);
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  const dayLabel = (number) => {
    const day = String(number).padStart(2, "0");
    const locale = document.documentElement.lang || "ja";
    if (locale === "ko") return `${number}일차`;
    if (locale === "zh-CN") return `第 ${day} 天`;
    if (locale === "zh-TW") return `第 ${day} 天`;
    if (locale === "th") return `วันที่ ${day}`;
    if (locale === "ja") return `${number}日目`;
    return `DAY\n${day}`;
  };
  const recommendedLabel = () => {
    const locale = document.documentElement.lang || "ja";
    if (locale === "ko") return "추천 스폿";
    if (locale === "zh-CN") return "推荐景点";
    if (locale === "zh-TW") return "推薦景點";
    if (locale === "th") return "จุดแนะนำ";
    if (locale === "en") return "Recommended spot";
    return "おすすめスポット";
  };

  function render(raw) {
    root.replaceChildren();
    const events = [];
    let currentDay = null;
    let currentSection = null;
    const addSection = (title) => {
      currentSection = { type: "section", title, blocks: [] };
      if (currentDay) currentDay.sections.push(currentSection);
      else events.push(currentSection);
    };
    const addBlock = (type, text) => {
      if (!currentSection) addSection(currentDay ? "旅の流れ" : "旅のハイライト");
      currentSection.blocks.push({ type, text: clean(text) });
    };

    for (const rawLine of raw.replace(/\r/g, "").split("\n")) {
      const line = rawLine.trim();
      if (!line) continue;
      const heading = line.match(/^#{1,6}\s+(.+)$/);
      const headingText = heading ? clean(heading[1]) : clean(line);
      const day = dayMatch(headingText);
      if (day) {
        currentDay = { type: "day", number: day.number, title: day.title || "旅の予定", sections: [] };
        events.push(currentDay);
        currentSection = null;
        continue;
      }
      if (heading) {
        if (/^旅のしおり/.test(headingText)) continue;
        if (isTimeSection(headingText) && currentDay) addSection(headingText);
        else { currentDay = null; addSection(headingText); }
        continue;
      }
      if (/^(?:第\s*)?\d+\s*日目/.test(line) || /^Day\s*\d+/i.test(line)) {
        const parsed = dayMatch(line.replace(/^[#*\s]+/, ""));
        if (parsed) {
          currentDay = { type: "day", number: parsed.number, title: parsed.title || "旅の予定", sections: [] };
          events.push(currentDay);
          currentSection = null;
          continue;
        }
      }
      const period = line.match(/^(午前|朝|昼|昼食|ランチ|午後|夕方|夜|夕食|移動|宿泊|朝食|morning|breakfast|lunch|afternoon|evening|night|transport|accommodation|오전|아침|점심|오후|저녁|이동|숙박|早餐|早上|上午|中午|午餐|下午|傍晚|晚上|交通|住宿|อาหารเช้า|เช้า|เที่ยง|บ่าย|เย็น|ค่ำ|การเดินทาง|ที่พัก)\s*[:：]/i);
      if (period && currentDay) {
        addSection(period[1]);
        const rest = line.slice(period[0].length).trim();
        if (rest) addBlock("paragraph", rest);
        continue;
      }
      const bullet = line.match(/^(?:[-*・•]|\d+[.)、])\s*(.+)$/);
      if (bullet) addBlock("item", bullet[1]);
      else addBlock("paragraph", line.replace(/^>\s*/, ""));
    }

    const renderSection = (section, isDaySection = false) => {
      const box = make("section", isDaySection ? "itinerary-period" : "itinerary-note");
      if (section.title) box.append(make("h4", "", section.title));
      let stops = null;
      let currentStop = null;
      for (const block of section.blocks) {
        if (block.type === "item") {
          if (!stops) { stops = make("div", "itinerary-stops"); box.append(stops); }
          const listingMarker = block.text.match(/\[\[TABIDEA_LISTING_ID:(\d+)\]\]/);
          const isRecommended = /おすすめスポット|recommended\s+spot|추천\s*스폿|추천\s*장소|推荐景点|推薦景點|จุดแนะนำ/i.test(block.text);
          currentStop = make("article", `itinerary-stop${isRecommended ? " itinerary-stop-recommended" : ""}`);
          const title = make("div", "itinerary-stop-title");
          const timed = block.text.match(/^(\d{1,2}[:：]\d{2})\s*[｜|—–-]\s*(.+)$/);
          let stopName = timed ? timed[2] : block.text;
          stopName = stopName.replace(/\s*\[\[TABIDEA_LISTING_ID:\d+\]\]/g, "");
          stopName = stopName.replace(/\s*[\[【(（]?(?:おすすめスポット|recommended\s+spot|추천\s*스폿|추천\s*장소|推荐景点|推薦景點|จุดแนะนำ)[\]】)）]?/ig, "").trim();
          if (timed) title.append(make("span", "itinerary-time", timed[1]));
          if (isRecommended && listingMarker && root.dataset.listingUrlTemplate) {
            const link = make("a", "itinerary-stop-link", stopName);
            const listingUrl = new URL(root.dataset.listingUrlTemplate, window.location.href);
            listingUrl.pathname = listingUrl.pathname.replace(/\/0$/, `/${listingMarker[1]}`);
            link.href = listingUrl.href;
            title.append(link);
          } else title.append(make("span", "itinerary-stop-name", stopName));
          if (isRecommended) title.append(make("span", "itinerary-recommended-badge", recommendedLabel()));
          currentStop.append(title);
          stops.append(currentStop);
        } else if (currentStop) currentStop.append(make("p", "", block.text));
        else box.append(make("p", isDaySection ? "itinerary-copy" : "", block.text));
      }
      return box;
    };

    for (const event of events) {
      if (event.type === "day") {
        const card = make("article", "itinerary-day");
        const head = make("header", "itinerary-day-head");
        head.append(make("span", "itinerary-day-number", dayLabel(event.number)));
        head.append(make("h3", "", event.title));
        card.append(head);
        const sections = make("div", "itinerary-sections");
        for (const section of event.sections) sections.append(renderSection(section, true));
        card.append(sections);
        root.append(card);
      } else root.append(renderSection(event));
    }
    if (!events.length) root.append(make("p", "itinerary-copy", raw));
  }

  render(source.content.textContent.trim());
  document.addEventListener("tabidea:plan-translated", (event) => render(event.detail?.text || source.content.textContent.trim()));
})();
