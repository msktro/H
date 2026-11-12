(() => {
  const menus = [...document.querySelectorAll(".site-menu, .home-menu")];
  if (!menus.length) return;

  document.addEventListener("pointerdown", (event) => {
    menus.forEach((menu) => {
      if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const openMenu = menus.find((menu) => menu.open);
    if (!openMenu) return;
    openMenu.open = false;
    openMenu.querySelector("summary")?.focus();
  });
})();
