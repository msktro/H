(() => {
  const container = document.getElementById("group-invite-qr");
  if (!container) return;

  const inviteUrl = container.dataset.inviteUrl;
  if (!inviteUrl || typeof QRCode === "undefined") {
    container.textContent = "QRコードを表示できません。招待リンクを使ってください。";
    return;
  }

  new QRCode(container, {
    text: inviteUrl,
    width: 192,
    height: 192,
    colorDark: "#173d34",
    colorLight: "#ffffff",
    correctLevel: QRCode.CorrectLevel.M
  });
})();
