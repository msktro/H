(() => {
  const storageKey = "tabidea.recovery-code.once";
  const emailStorageKey = "tabidea.recovery-code.email.once";
  const url = new URL(window.location.href);
  const saved = url.searchParams.get("recovery_code_saved") === "1";
  const locale = (() => {
    try { return localStorage.getItem("tabidea-language") || "ja"; }
    catch (_error) { return "ja"; }
  })();
  const alertCopy = {
    en: ["Recovery code saved. Store it somewhere safe so you do not forget it.", "Recovery code", "It is saved in this browser. Other people using this device may be able to view it."],
    ko: ["복구 코드를 설정했습니다. 잊지 않도록 안전한 곳에 보관하세요.", "복구 코드", "이 브라우저에 저장됩니다. 이 기기를 사용하는 다른 사람도 볼 수 있습니다."],
    "zh-CN": ["恢复码已设置。请妥善保存，以免忘记。", "恢复码", "此代码保存在此浏览器中。使用此设备的其他人可能也能看到。"],
    "zh-TW": ["復原碼已設定。請妥善保存，以免忘記。", "復原碼", "此代碼會儲存在此瀏覽器中。使用此裝置的其他人也可能看得到。"],
    th: ["ตั้งค่ารหัสกู้คืนแล้ว โปรดเก็บไว้ในที่ปลอดภัยเพื่อไม่ให้ลืม", "รหัสกู้คืน", "บันทึกไว้ในเบราว์เซอร์นี้ ผู้ใช้อุปกรณ์นี้คนอื่นอาจดูได้"]
  }[locale] || ["復旧コードを設定しました。忘れないよう安全な場所に保存してください。", "復旧コード", "このブラウザー内に保存しています。共用端末では他の人に見られる可能性があります。"];
  const helpMessage = {
    en: "Enter your email address and select this link to view the recovery code saved in this browser. If it is not saved here, you can change it from your profile while signed in.",
    ko: "이 브라우저에 저장된 복구 코드를 보려면 이메일 주소를 입력하고 이 링크를 선택하세요. 여기에 저장되어 있지 않으면 로그인한 뒤 프로필에서 변경할 수 있습니다.",
    "zh-CN": "输入邮箱并点击此链接，可查看保存在此浏览器中的恢复码。如果此处没有保存，登录后可在个人资料中更改。",
    "zh-TW": "輸入電子郵件並點選此連結，可查看儲存在此瀏覽器中的復原碼。如果此處沒有儲存，登入後可在個人資料中變更。",
    th: "กรอกอีเมลแล้วเลือกลิงก์นี้เพื่อดูรหัสกู้คืนที่บันทึกไว้ในเบราว์เซอร์นี้ หากไม่มีรหัสบันทึกไว้ ให้เข้าสู่ระบบแล้วเปลี่ยนในโปรไฟล์"
  }[locale] || "メールアドレスを入力してこのリンクを押すと、このブラウザーに保存した復旧コードを表示します。保存されていない場合は、ログイン後にプロフィールから変更できます。";

  document.querySelectorAll("[data-recovery-code-help]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const emailInput = document.getElementById("reset-email");
      const email = (emailInput?.value || "").trim().toLowerCase();
      let code = null;
      if (email) {
        try { code = localStorage.getItem(`tabidea.recovery-code:${email}`); } catch (_error) {}
      }
      if (code) window.alert(`${alertCopy[1]}: ${code}`);
      else window.alert(helpMessage);
    });
  });

  if (saved) {
    const code = sessionStorage.getItem(storageKey);
    const email = sessionStorage.getItem(emailStorageKey);
    sessionStorage.removeItem(storageKey);
    sessionStorage.removeItem(emailStorageKey);
    url.searchParams.delete("recovery_code_saved");
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    if (code) {
      if (email) {
        try { localStorage.setItem(`tabidea.recovery-code:${email}`, code); } catch (_error) {}
      }
      window.alert(`${alertCopy[0]}\n\n${alertCopy[1]}: ${code}\n\n${alertCopy[2]}`);
    }
  } else {
    sessionStorage.removeItem(storageKey);
    sessionStorage.removeItem(emailStorageKey);
  }

  document.querySelectorAll('form input[name="recovery_password"]').forEach((input) => {
    const form = input.form;
    if (!form) return;
    form.addEventListener("submit", () => {
      const email = (form.querySelector('input[name="email"]')?.value || form.dataset.recoveryEmail || "").trim().toLowerCase();
      if (input.value) {
        sessionStorage.setItem(storageKey, input.value);
        sessionStorage.setItem(emailStorageKey, email);
      } else {
        sessionStorage.removeItem(storageKey);
        sessionStorage.removeItem(emailStorageKey);
      }
    });
  });
})();
