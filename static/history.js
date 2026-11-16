(() => {
  const cards = [...document.querySelectorAll('.history-card')];
  if (!cards.length) return;
  let openMenu = null;
  const closeMenu = () => {
    if (!openMenu) return;
    const menu = openMenu;
    menu.hidden = true;
    menu.style.left = '';
    menu.style.top = '';
    menu.style.visibility = '';
    const origin = menu._historyOrigin;
    if (origin) origin.appendChild(menu);
    menu._historyOrigin = null;
    openMenu = null;
  };
  const showMenu = (card, x, y, focusMenu = false) => {
    closeMenu();
    const menu = card.querySelector('.history-context-menu');
    if (!menu) return;
    menu._historyOrigin = card;
    document.body.appendChild(menu);
    menu.hidden = false;
    menu.style.visibility = 'hidden';
    menu.style.left = '0px';
    menu.style.top = '0px';
    openMenu = menu;
    window.requestAnimationFrame(() => {
      if (openMenu !== menu) return;
      const rect = menu.getBoundingClientRect();
      const left = Math.max(8, Math.min(x, window.innerWidth - rect.width - 8));
      const top = Math.max(8, Math.min(y, window.innerHeight - rect.height - 8));
      menu.style.left = `${left}px`;
      menu.style.top = `${top}px`;
      menu.style.visibility = 'visible';
      if (focusMenu) menu.querySelector('button')?.focus({ preventScroll: true });
    });
  };
  cards.forEach(card => {
    card.addEventListener('contextmenu', event => {
      event.preventDefault();
      showMenu(card, event.clientX, event.clientY);
    });
    card.addEventListener('keydown', event => {
      if ((event.key === 'F10' && event.shiftKey) || event.key === 'ContextMenu') {
        event.preventDefault();
        const rect = card.getBoundingClientRect();
        showMenu(card, rect.left + 16, rect.top + 16, true);
      }
    });
  });
  document.addEventListener('click', event => {
    if (openMenu && !openMenu.contains(event.target)) closeMenu();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeMenu();
  });
  window.addEventListener('scroll', closeMenu, { passive: true });
  window.addEventListener('resize', closeMenu);
})();
