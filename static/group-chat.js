(() => {
  const root = document.getElementById("group-chat");
  if (!root) return;

  const list = document.getElementById("group-chat-messages");
  const form = document.getElementById("group-chat-form");
  const input = document.getElementById("group-chat-input");
  const sendButton = document.getElementById("group-chat-send");
  const status = document.getElementById("group-chat-status");
  const seen = new Set();
  let lastId = 0;
  let sending = false;
  let polling = false;

  function formatTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? ""
      : new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(date);
  }

  function addMessage(message) {
    const id = Number(message.id);
    if (!id || seen.has(id)) return;
    seen.add(id);
    lastId = Math.max(lastId, id);
    document.getElementById("group-chat-empty")?.remove();

    const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 90;
    const article = document.createElement("article");
    article.className = `chat-message${Number(message.user_id) === Number(root.dataset.userId) ? " mine" : ""}`;
    article.dataset.messageId = String(id);

    const meta = document.createElement("div");
    meta.className = "chat-message-meta";
    const avatar = document.createElement("span");
    avatar.className = "chat-avatar";
    avatar.textContent = message.avatar || "👤";
    const username = document.createElement("b");
    username.textContent = message.username || "メンバー";
    const time = document.createElement("time");
    time.dateTime = message.created_at || "";
    time.textContent = formatTime(message.created_at);
    meta.append(avatar, username, time);

    const content = document.createElement("p");
    content.dataset.noTranslate = "";
    content.textContent = message.content || "";
    article.append(meta, content);
    list.appendChild(article);
    if (nearBottom) list.scrollTop = list.scrollHeight;
  }

  document.querySelectorAll("#group-chat-messages [data-message-id]").forEach((element) => {
    const id = Number(element.dataset.messageId);
    if (id) {
      seen.add(id);
      lastId = Math.max(lastId, id);
      const time = element.querySelector("time");
      if (time) time.textContent = formatTime(time.dateTime);
    }
  });
  list.scrollTop = list.scrollHeight;
  document.addEventListener("group:tab-shown", (event) => {
    if (event.detail === "chat") {
      list.scrollTop = list.scrollHeight;
      pollMessages();
    }
  });

  async function pollMessages() {
    if (polling || document.visibilityState !== "visible") return;
    polling = true;
    try {
      const response = await fetch(`${root.dataset.messagesUrl}?after=${lastId}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "メッセージを取得できませんでした。");
      data.messages.forEach(addMessage);
      status.textContent = "";
    } catch (_error) {
      status.textContent = "チャットに接続できません。通信状態を確認しています…";
    } finally {
      polling = false;
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const content = input.value.trim();
    if (!content || sending) return;
    sending = true;
    sendButton.disabled = true;
    input.disabled = true;
    status.textContent = "送信しています…";
    try {
      const response = await fetch(root.dataset.messagesUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": root.dataset.csrf,
          Accept: "application/json",
        },
        body: JSON.stringify({ content }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "送信できませんでした。");
      addMessage(data.message);
      input.value = "";
      status.textContent = "";
    } catch (error) {
      status.textContent = error.message || "送信できませんでした。通信状態を確認してください。";
    } finally {
      sending = false;
      sendButton.disabled = false;
      input.disabled = false;
      input.focus();
    }
  });

  window.setInterval(pollMessages, 3000);
})();
