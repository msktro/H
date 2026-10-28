(() => {
  const root = document.getElementById("group-chat");
  if (!root) return;

  const list = document.getElementById("group-chat-messages");
  const form = document.getElementById("group-chat-form");
  const input = document.getElementById("group-chat-input");
  const sendButton = document.getElementById("group-chat-send");
  const status = document.getElementById("group-chat-status");
  const stampToggle = document.getElementById("chat-stamp-toggle");
  const stampPicker = document.getElementById("chat-stamp-picker");
  const notificationToggle = document.getElementById("group-chat-notifications");
  const notificationKey = `group-chat-notifications:${root.dataset.userId}`;
  const reactionEmojis = ["👍", "❤️", "😂", "😮", "👏"];
  let activeReactionMessageId = null;
  const seen = new Set();
  let lastId = 0;
  let sending = false;
  let polling = false;
  let markingRead = false;
  const readMarked = new Set();

  function chatIsActive() {
    const panel = document.querySelector('[data-group-panel="chat"]');
    return document.visibilityState === "visible" && panel && !panel.hidden;
  }

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
    if (message.is_stamp) article.classList.add("stamp-message");
    article.dataset.messageId = String(id);
    article.dataset.userId = String(message.user_id);

    const meta = document.createElement("div");
    meta.className = "chat-message-meta";
    const avatar = document.createElement("span");
    avatar.className = "chat-avatar";
    if (message.avatar_image_url) {
      const avatarImage = document.createElement("img");
      avatarImage.src = message.avatar_image_url;
      avatarImage.alt = "";
      avatarImage.className = "avatar-image";
      avatar.appendChild(avatarImage);
    } else {
      avatar.textContent = message.avatar || "👤";
    }
    const username = document.createElement("b");
    username.textContent = message.username || "メンバー";
    const time = document.createElement("time");
    time.dateTime = message.created_at || "";
    time.textContent = formatTime(message.created_at);
    meta.append(avatar, username, time);

    const content = document.createElement("p");
    content.dataset.noTranslate = "";
    content.textContent = message.is_deleted ? "このメッセージは送信取り消しされました。" : (message.content || "");
    article.append(meta, content);
    if (Number(message.user_id) === Number(root.dataset.userId) && !message.is_deleted) {
      const unsend = document.createElement("button");
      unsend.type = "button";
      unsend.className = "chat-unsend-button";
      unsend.dataset.unsendMessage = String(id);
      unsend.textContent = "送信取り消し";
      article.appendChild(unsend);
    }
    const isOwnMessage = Number(message.user_id) === Number(root.dataset.userId);
    let reactionTrigger = null;
    if (!isOwnMessage && !message.is_deleted) {
      reactionTrigger = document.createElement("button");
      reactionTrigger.type = "button";
      reactionTrigger.className = "chat-reaction-trigger";
      reactionTrigger.dataset.reactionTrigger = String(id);
      reactionTrigger.setAttribute("aria-label", "リアクションを選ぶ");
      reactionTrigger.textContent = "＋";
    }
    const reactions = document.createElement("div");
    reactions.className = "chat-reactions";
    reactions.dataset.reactionsFor = String(id);
    if (reactionTrigger) article.appendChild(reactionTrigger);
    article.appendChild(reactions);
    renderReactions(article, message.is_deleted ? {} : (message.reaction_counts || {}), message.my_reaction || "");
    if (Number(message.user_id) === Number(root.dataset.userId)) {
      const readState = document.createElement("small");
      readState.className = "chat-read-state";
      readState.dataset.readFor = String(id);
      readState.textContent = message.read_count ? `既読 ${message.read_count}` : "";
      article.appendChild(readState);
    }
    list.appendChild(article);
    if (nearBottom) list.scrollTop = list.scrollHeight;
  }

  function updateReadStatus(readStatus) {
    Object.entries(readStatus || {}).forEach(([id, count]) => {
      const label = list.querySelector(`[data-read-for="${id}"]`);
      if (label) label.textContent = count ? `既読 ${count}` : "";
    });
  }

  function applyMessageDeletion(message) {
    if (!message?.is_deleted) return;
    const article = list.querySelector(`[data-message-id="${message.id}"]`);
    if (!article) return;
    const content = article.querySelector("p[data-no-translate]");
    if (content) content.textContent = "このメッセージは送信取り消しされました。";
    article.querySelector("[data-unsend-message]")?.remove();
    article.querySelector("[data-reaction-trigger]")?.remove();
    const reactions = article.querySelector(".chat-reactions");
    if (reactions) {
      reactions.replaceChildren();
      reactions.hidden = true;
    }
    article.classList.remove("stamp-message");
  }

  function updateUnreadBadge(amount, direction = -1) {
    if (!amount) return;
    document.querySelectorAll("[data-group-notification-badge]").forEach((badge) => {
      const next = Math.max(0, Number(badge.dataset.count || 0) + direction * amount);
      badge.dataset.count = String(next);
      badge.textContent = next ? String(next) : "";
      badge.hidden = next === 0;
    });
    document.querySelectorAll("[data-group-chat-badge]").forEach((badge) => {
      if (Number(badge.dataset.groupId) !== Number(root.dataset.groupId)) return;
      const next = Math.max(0, Number(badge.dataset.count || 0) + direction * amount);
      badge.dataset.count = String(next);
      badge.textContent = next ? String(next) : "";
      badge.hidden = next === 0;
      badge.setAttribute("aria-label", `未読メッセージ ${next}件`);
    });
    root.dataset.unreadCount = String(Math.max(0, Number(root.dataset.unreadCount || 0) + direction * amount));
  }

  function renderReactions(article, counts, mine) {
    const container = article.querySelector(".chat-reactions");
    if (!container) return;
    container.replaceChildren();
    Object.entries(counts).forEach(([emoji, count]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `chat-reaction${mine === emoji ? " selected" : ""}`;
      button.disabled = Number(article.dataset.userId) === Number(root.dataset.userId);
      button.dataset.reactionEmoji = emoji;
      button.setAttribute("aria-pressed", String(mine === emoji));
      button.textContent = `${emoji} ${count}`;
      container.appendChild(button);
    });
    container.hidden = container.childElementCount === 0;
  }

  function updateReactionStatus(reactionStatus) {
    Object.entries(reactionStatus || {}).forEach(([id, state]) => {
      const article = list.querySelector(`[data-message-id="${id}"]`);
      if (article) renderReactions(article, state.counts || {}, state.mine || "");
    });
  }

  async function toggleReaction(messageId, emoji) {
    try {
      const response = await fetch(`${root.dataset.reactionsUrl}/${messageId}/reactions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": root.dataset.csrf,
          Accept: "application/json",
        },
        body: JSON.stringify({ emoji }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "リアクションを送信できませんでした。");
      const article = list.querySelector(`[data-message-id="${messageId}"]`);
      if (article) renderReactions(article, data.reaction_status.counts, data.reaction_status.mine);
      status.textContent = "";
    } catch (error) {
      status.textContent = error.message || "リアクションを送信できませんでした。";
    }
  }

  const reactionMenu = document.createElement("div");
  reactionMenu.className = "chat-reaction-menu";
  reactionMenu.hidden = true;
  reactionMenu.setAttribute("role", "menu");
  reactionEmojis.forEach((emoji) => {
    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.textContent = emoji;
    button.addEventListener("click", () => {
      if (activeReactionMessageId) toggleReaction(activeReactionMessageId, emoji);
      reactionMenu.hidden = true;
    });
    reactionMenu.appendChild(button);
  });
  document.body.appendChild(reactionMenu);

  function openReactionMenu(messageId, x, y) {
    activeReactionMessageId = Number(messageId);
    reactionMenu.hidden = false;
    const left = Math.max(8, Math.min(x, window.innerWidth - 220));
    const top = Math.max(8, Math.min(y, window.innerHeight - 64));
    reactionMenu.style.left = `${left}px`;
    reactionMenu.style.top = `${top}px`;
    reactionMenu.querySelector("button")?.focus();
  }

  list.addEventListener("contextmenu", (event) => {
    const article = event.target.closest(".chat-message");
    if (!article) return;
    event.preventDefault();
    if (Number(article.dataset.userId) === Number(root.dataset.userId)) return;
    openReactionMenu(article.dataset.messageId, event.clientX, event.clientY);
  });

  list.addEventListener("click", (event) => {
    const unsend = event.target.closest("[data-unsend-message]");
    if (unsend) {
      unsendGroupMessage(unsend.dataset.unsendMessage, unsend);
      return;
    }
    const trigger = event.target.closest("[data-reaction-trigger]");
    if (trigger) {
      const rect = trigger.getBoundingClientRect();
      openReactionMenu(trigger.dataset.reactionTrigger, rect.left, rect.bottom + 4);
      return;
    }
    const reaction = event.target.closest("[data-reaction-emoji]");
    if (reaction && !reaction.disabled) {
      const article = reaction.closest(".chat-message");
      toggleReaction(article.dataset.messageId, reaction.dataset.reactionEmoji);
    }
  });

  async function unsendGroupMessage(messageId, button) {
    if (!window.confirm("このメッセージの送信を取り消しますか？")) return;
    button.disabled = true;
    try {
      const response = await fetch(`${root.dataset.messagesUrl}/${messageId}/unsend`, {
        method: "POST",
        headers: { "X-CSRFToken": root.dataset.csrf, Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "送信を取り消せませんでした。");
      applyMessageDeletion(data.message);
      status.textContent = "メッセージの送信を取り消しました。";
    } catch (error) {
      status.textContent = error.message || "送信を取り消せませんでした。";
      button.disabled = false;
    }
  }

  function notificationsAreEnabled() {
    return localStorage.getItem(notificationKey) === "on";
  }

  function updateNotificationToggle() {
    if (!notificationToggle) return;
    notificationToggle.hidden = !("Notification" in window);
    notificationToggle.textContent = notificationsAreEnabled() ? "通知をオフ" : "通知をオン";
    notificationToggle.setAttribute("aria-pressed", String(notificationsAreEnabled()));
  }

  notificationToggle?.addEventListener("click", async () => {
    if (notificationsAreEnabled()) {
      localStorage.removeItem(notificationKey);
      status.textContent = "ブラウザ通知をオフにしました。";
    } else if ("Notification" in window) {
      const permission = Notification.permission === "granted"
        ? "granted"
        : await Notification.requestPermission();
      if (permission === "granted") {
        localStorage.setItem(notificationKey, "on");
        status.textContent = "このグループの新着メッセージを通知します。";
      } else {
        status.textContent = "ブラウザの設定で通知を許可してください。";
      }
    }
    updateNotificationToggle();
  });
  updateNotificationToggle();

  document.addEventListener("pointerdown", (event) => {
    if (!reactionMenu.hidden && !reactionMenu.contains(event.target) && !event.target.closest("[data-reaction-trigger]")) {
      reactionMenu.hidden = true;
    }
    if (stampPicker && !stampPicker.hidden && !stampPicker.contains(event.target) && event.target !== stampToggle) {
      stampPicker.hidden = true;
      stampToggle?.setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      reactionMenu.hidden = true;
      if (stampPicker) stampPicker.hidden = true;
      stampToggle?.setAttribute("aria-expanded", "false");
    }
  });

  stampToggle?.addEventListener("click", () => {
    stampPicker.hidden = !stampPicker.hidden;
    stampToggle.setAttribute("aria-expanded", String(!stampPicker.hidden));
  });
  stampPicker?.addEventListener("click", (event) => {
    const stampButton = event.target.closest("[data-chat-stamp]");
    if (!stampButton) return;
    const stamp = stampButton.dataset.chatStamp;
    const start = input.selectionStart ?? input.value.length;
    const end = input.selectionEnd ?? start;
    input.setRangeText(stamp, start, end, "end");
    input.focus();
    stampPicker.hidden = true;
    stampToggle?.setAttribute("aria-expanded", "false");
  });

  async function markVisibleMessagesRead() {
    if (markingRead || !chatIsActive()) return;
    const ids = [...list.querySelectorAll("[data-message-id]")]
      .filter((element) => Number(element.dataset.userId) !== Number(root.dataset.userId))
      .map((element) => Number(element.dataset.messageId))
      .filter((id) => id && !readMarked.has(id));
    if (!ids.length) return;
    markingRead = true;
    try {
      const response = await fetch(root.dataset.readUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": root.dataset.csrf,
          Accept: "application/json",
        },
        body: JSON.stringify({ message_ids: ids }),
      });
      if (response.ok) {
        ids.forEach((id) => readMarked.add(id));
        const data = await response.json();
        updateUnreadBadge(data.newly_read_count || 0);
      }
    } catch (_error) {
      // The next poll retries marking these messages as read.
    } finally {
      markingRead = false;
    }
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
    const canNotifyInBackground = "Notification" in window
      && notificationsAreEnabled()
      && Notification.permission === "granted";
    if (polling || (document.visibilityState !== "visible" && !canNotifyInBackground)) return;
    polling = true;
    try {
      const response = await fetch(`${root.dataset.messagesUrl}?after=${lastId}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "メッセージを取得できませんでした。");
      const incoming = data.messages.filter((message) =>
        Number(message.user_id) !== Number(root.dataset.userId) && !seen.has(Number(message.id)) && !message.is_deleted
      );
      data.messages.forEach(addMessage);
      (data.deleted_messages || []).forEach(applyMessageDeletion);
      if (!chatIsActive() && incoming.length) updateUnreadBadge(incoming.length, 1);
      if (document.visibilityState !== "visible" && !chatIsActive() && "Notification" in window && notificationsAreEnabled() && Notification.permission === "granted") {
        incoming.forEach((message) => {
          const notification = new Notification(`${root.dataset.groupName}: ${message.username}`, {
            body: message.content,
            tag: `group-${root.dataset.groupId}-${message.id}`,
          });
          notification.onclick = () => window.focus();
        });
      }
      updateReadStatus(data.read_status);
      updateReactionStatus(data.reaction_status);
      await markVisibleMessagesRead();
      status.textContent = "";
    } catch (_error) {
      status.textContent = "チャットに接続できません。通信状態を確認しています…";
    } finally {
      polling = false;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (chatIsActive()) pollMessages();
  });

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
