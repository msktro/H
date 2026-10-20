(() => {
  const button = document.querySelector("[data-copy-invite]");
  if (!button) return;

  const status = document.getElementById("invite-copy-status");
  const codeElement = document.getElementById(button.dataset.copyInvite);
  const translations = {
    ja: ["コードをコピー", "コピーしました", "招待コードをコピーしました。仲間に共有できます。", "コピーできませんでした。招待コードを選択してコピーしてください。"],
    en: ["Copy code", "Copied", "Invite code copied. Share it with your group.", "Could not copy. Select and copy the invite code manually."],
    ko: ["코드 복사", "복사했습니다", "초대 코드를 복사했습니다. 그룹에 공유하세요.", "복사하지 못했습니다. 초대 코드를 선택해 직접 복사하세요."],
    "zh-CN": ["复制代码", "已复制", "邀请码已复制，可以分享给好友。", "无法复制，请手动选择并复制邀请码。"],
    "zh-TW": ["複製代碼", "已複製", "邀請碼已複製，可以分享給好友。", "無法複製，請手動選取並複製邀請碼。"],
    th: ["คัดลอกรหัส", "คัดลอกแล้ว", "คัดลอกรหัสเชิญแล้ว แชร์ให้เพื่อนได้เลย", "คัดลอกไม่สำเร็จ โปรดเลือกและคัดลอกรหัสเชิญด้วยตนเอง"]
  };
  let locale = document.getElementById("language-selector")?.value || "ja";
  let resetTimer;

  function message(index) {
    return (translations[locale] || translations.ja)[index];
  }
  function resetButton() {
    button.textContent = message(0);
  }
  document.addEventListener("tabidea:language-changed", (event) => {
    locale = event.detail.locale;
    resetButton();
    if (status) status.textContent = "";
  });

  async function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
      return;
    }

    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand("copy");
    field.remove();
    if (!copied) throw new Error("Clipboard copy failed");
  }

  button.addEventListener("click", async () => {
    if (!codeElement) return;
    try {
      await copyText(codeElement.textContent.trim());
      button.textContent = message(1);
      if (status) status.textContent = message(2);
    } catch {
      if (status) status.textContent = message(3);
    }
    window.clearTimeout(resetTimer);
    resetTimer = window.setTimeout(resetButton, 2200);
  });
})();
