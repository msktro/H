(() => {
  const root = document.getElementById("group-notifications");
  if (!root) return;

  let cursor = Number(root.dataset.cursor || 0);
  let polling = false;
  let toastContainer = null;

  function updateBadges(data) {
    const total = Number(data.unread_total || 0);
    document.querySelectorAll("[data-group-notification-badge]").forEach((badge) => {
      badge.dataset.count = String(total);
      badge.textContent = total ? String(total) : "";
      badge.hidden = total === 0;
    });

    const commentCount = Number(data.unread_journey_comment_count || 0);
    document.querySelectorAll("[data-journey-comment-dot]").forEach((dot) => {
      dot.hidden = commentCount === 0;
      dot.setAttribute("aria-label", commentCount ? `新着コメント ${commentCount}件` : "");
    });
    document.querySelectorAll("[data-unread-notice-dot]").forEach((dot) => {
      const releaseUnread = dot.dataset.releaseUnread === "true";
      dot.hidden = !releaseUnread && commentCount === 0;
    });
    const storyCounts = data.unread_journey_comment_counts || {};
    document.querySelectorAll("[data-my-posts-comment-dot]").forEach((dot) => {
      dot.hidden = commentCount === 0;
      dot.setAttribute("aria-label", commentCount ? `未読コメント ${commentCount}件` : "");
    });
    document.querySelectorAll("[data-story-comment-dot]").forEach((dot) => {
      const count = Number(storyCounts[dot.dataset.storyId] || 0);
      dot.hidden = count === 0;
      dot.setAttribute("aria-label", count ? `未読コメント ${count}件` : "");
    });
    document.querySelectorAll("[data-story-comment-count]").forEach((badge) => {
      const count = Number(storyCounts[badge.dataset.storyId] || 0);
      badge.hidden = count === 0;
      const number = badge.querySelector("[data-story-comment-number]");
      if (number) number.textContent = count ? String(count) : "";
    });
    const counts = data.unread_counts || {};
    document.querySelectorAll("[data-group-unread-badge]").forEach((badge) => {
      const count = Number(counts[badge.dataset.groupId] || 0);
      badge.textContent = count ? String(count) : "";
      badge.hidden = count === 0;
      badge.setAttribute("aria-label", `未読メッセージ ${count}件`);
    });
    document.querySelectorAll("[data-group-chat-badge]").forEach((badge) => {
      const count = Number(counts[badge.dataset.groupId] || 0);
      badge.dataset.count = String(count);
      badge.textContent = count ? String(count) : "";
      badge.hidden = count === 0;
      badge.setAttribute("aria-label", `未読メッセージ ${count}件`);
    });
  }

  function chatIsOpenFor(groupId) {
    const chat = document.getElementById("group-chat");
    const panel = document.querySelector('[data-group-panel="chat"]');
    return chat && Number(chat.dataset.groupId) === Number(groupId)
      && panel && !panel.hidden && document.visibilityState === "visible";
  }

  function showToast(message) {
    if (document.visibilityState !== "visible" || chatIsOpenFor(message.group_id)) return;
    if (!toastContainer) {
      toastContainer = document.createElement("div");
      toastContainer.className = "group-notification-toasts";
      toastContainer.setAttribute("role", "status");
      toastContainer.setAttribute("aria-live", "polite");
      toastContainer.setAttribute("aria-relevant", "additions");
      document.body.appendChild(toastContainer);
    }

    const toast = document.createElement("article");
    toast.className = "group-notification-toast";
    const heading = document.createElement("strong");
    heading.className = "group-notification-toast-heading";
    heading.textContent = `${message.group_name || "グループ"} · ${message.username || "メンバー"}`;
    const body = document.createElement("span");
    body.className = "group-notification-toast-body";
    body.textContent = message.content || "新しいメッセージが届きました。";
    toast.append(heading, body);
    toastContainer.appendChild(toast);

    window.setTimeout(() => {
      toast.classList.add("is-leaving");
      window.setTimeout(() => toast.remove(), 220);
    }, 3000);
  }

  async function poll() {
    if (polling || document.visibilityState !== "visible") return;
    polling = true;
    try {
      const response = await fetch(`${root.dataset.pollUrl}?after=${cursor}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) return;
      const data = await response.json();
      cursor = Math.max(cursor, Number(data.cursor || cursor));
      updateBadges(data);
      root.dataset.commentCount = String(Number(data.unread_journey_comment_count || 0));
      (data.messages || []).forEach(showToast);
    } catch (_error) {
      // Keep the current badges and retry on the next interval.
    } finally {
      polling = false;
    }
  }

  poll();
  window.setInterval(poll, 3000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") poll();
  });
})();
