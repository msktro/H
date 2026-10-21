(() => {
  const menu = document.querySelector(".site-menu");
  if (!menu) return;

  document.addEventListener("pointerdown", (event) => {
    if (menu.open && !menu.contains(event.target)) menu.open = false;
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !menu.open) return;
    menu.open = false;
    menu.querySelector(".menu-toggle")?.focus();
  });
})();
