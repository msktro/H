(() => {
  let typed = "";
  let opened = false;
  document.addEventListener("keydown", event => {
    if (opened || event.ctrlKey || event.altKey || event.metaKey || event.key.length !== 1) return;
    const active = document.activeElement;
    if (active?.matches("input, textarea, select, [contenteditable='true']")) return;
    if (!/^[a-z]$/i.test(event.key)) { typed = ""; return; }
    typed = (typed + event.key.toLowerCase()).slice(-6);
    if (typed !== "masaki") return;
    opened = true;
    const welcome = document.createElement("div");
    welcome.className = "home-minigame-welcome";
    welcome.setAttribute("role", "status");
    welcome.setAttribute("aria-live", "assertive");
    welcome.innerHTML = '<span class="home-minigame-welcome-plane" aria-hidden="true">✈</span><span>ミニゲームへようこそ</span>';
    document.body.append(welcome);
    window.setTimeout(() => window.location.assign("/__tabidea_minigame__"), 1300);
  });
})();
