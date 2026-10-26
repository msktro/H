(() => {
  const root = document.getElementById("travel-support");
  if (!root) return;

  const planSelect = document.getElementById("support-plan");
  const planLink = document.getElementById("support-open-plan");
  const planContext = document.getElementById("support-context");
  const planPreview = document.getElementById("support-plan-preview");
  const messageList = document.getElementById("support-messages");
  const form = document.getElementById("support-form");
  const input = document.getElementById("support-input");
  const sendButton = document.getElementById("support-send");
  const status = document.getElementById("support-status");
  const plans = Array.from(document.querySelectorAll("#support-plan-data template"));
  let conversation = [];
  let sending = false;

  function selectedPlan() {
    return plans.find((item) => item.dataset.planId === planSelect.value);
  }

  function appendMessage(role, content, extraClass = "") {
    const message = document.createElement("div");
    message.className = `support-message ${role} ${extraClass}`.trim();
    message.textContent = content;
    messageList.appendChild(message);
    messageList.scrollTop = messageList.scrollHeight;
  }

  function updatePlan() {
    const plan = selectedPlan();
    conversation = [];
    messageList.replaceChildren();
    const welcome = document.createElement("div");
    welcome.className = "support-welcome";
    const title = document.createElement("b");
    title.textContent = "Tabidea AI";
    const text = document.createElement("p");
    text.textContent = plan
      ? `${plan.dataset.planDestination}の旅行プランに沿ってお手伝いします。知りたいことを入力してください。`
      : "相談する旅行プランを選択してください。";
    welcome.append(title, text);
    messageList.appendChild(welcome);
    if (plan) {
      planContext.textContent = `${plan.dataset.planDestination} · ${plan.dataset.planDays}日 · ${plan.dataset.planPeople}名`;
      planPreview.textContent = plan.content.textContent.trim() || "プラン内容が登録されていません。";
      planLink.href = plan.dataset.planUrl;
      planLink.hidden = false;
    } else {
      planContext.textContent = "旅行プランを選択してください。";
      planPreview.textContent = "プランを選ぶと、ここに内容が表示されます。";
      planLink.hidden = true;
    }
    status.textContent = "";
  }

  planSelect.addEventListener("change", updatePlan);
  document.querySelectorAll("[data-prompt]").forEach((button) => {
    button.addEventListener("click", () => {
      input.value = button.dataset.prompt;
      input.focus();
      form.requestSubmit();
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    const plan = selectedPlan();
    if (sending || !question || !plan) return;

    sending = true;
    sendButton.disabled = true;
    input.disabled = true;
    planSelect.disabled = true;
    status.textContent = "AIが回答を作成しています…";
    while (conversation.length && (
      conversation.length >= 11 ||
      conversation.reduce((total, message) => total + message.content.length, 0) + question.length > 6500
    )) conversation.shift();
    conversation.push({ role: "user", content: question });
    appendMessage("user", question);
    input.value = "";

    try {
      const response = await fetch(root.dataset.chatUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": root.dataset.csrf,
        },
        body: JSON.stringify({ plan_id: plan.dataset.planId, messages: conversation }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "回答を取得できませんでした。");
      conversation.push({ role: "assistant", content: data.answer });
      appendMessage("assistant", data.answer);
      status.textContent = "";
    } catch (error) {
      conversation.pop();
      appendMessage("error", error.message || "通信に失敗しました。少し待って再度お試しください。", "error");
      status.textContent = "送信に失敗しました。質問を確認して、もう一度お試しください。";
      input.value = question;
    } finally {
      sending = false;
      sendButton.disabled = false;
      input.disabled = false;
      planSelect.disabled = false;
      input.focus();
    }
  });

  updatePlan();
})();
