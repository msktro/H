(() => {
  const plane = document.querySelector("[data-home-idle-plane]");
  if (!plane || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const idleDelay = 60_000;
  const crashDuration = 1_100;
  const returnDelay = 2_000;
  let idleTimer = 0;
  let isAnimating = false;
  let hasCrashed = false;

  function setInteractive(enabled) {
    plane.disabled = !enabled;
    if (enabled) {
      plane.removeAttribute("aria-hidden");
      plane.setAttribute("aria-label", "飛行中の飛行機をクリック");
    } else {
      plane.setAttribute("aria-hidden", "true");
      plane.setAttribute("aria-label", "飛行中の飛行機");
    }
  }

  function resetInlineMotion() {
    plane.style.animation = "";
    plane.style.transform = "";
    plane.style.opacity = "";
    plane.style.transition = "";
  }

  function scheduleFlight() {
    window.clearTimeout(idleTimer);
    if (document.visibilityState !== "visible" || isAnimating) return;
    idleTimer = window.setTimeout(() => {
      if (document.visibilityState !== "visible") return scheduleFlight();
      isAnimating = true;
      hasCrashed = false;
      setInteractive(true);
      plane.classList.add("is-flying");
    }, idleDelay);
  }

  function crashAndReturn(event) {
    if (!plane.classList.contains("is-flying") || hasCrashed) return;
    event.preventDefault();
    event.stopPropagation();
    hasCrashed = true;

    const currentTransform = window.getComputedStyle(plane).transform;
    const currentOpacity = window.getComputedStyle(plane).opacity;
    const fallenTransform = new DOMMatrix(currentTransform);
    fallenTransform.m42 += 82;
    plane.style.animation = "none";
    plane.style.transform = currentTransform;
    plane.style.opacity = currentOpacity;
    setInteractive(false);
    plane.classList.remove("is-flying");
    void plane.offsetWidth;
    plane.classList.add("is-crashing");
    window.requestAnimationFrame(() => {
      plane.style.transform = fallenTransform.toString();
      plane.style.opacity = "0";
    });

    window.setTimeout(() => {
      plane.classList.remove("is-crashing");
      plane.style.transition = "none";
      plane.style.transform = "translate3d(-70px,-12px,0) rotate(-10deg)";
      plane.style.opacity = "0";
      void plane.offsetWidth;
      plane.style.transition = "";
      window.setTimeout(() => {
        plane.style.animation = "";
        plane.classList.add("is-returning");
      }, returnDelay);
    }, crashDuration);
  }

  plane.addEventListener("click", crashAndReturn);
  plane.addEventListener("animationend", (event) => {
    if (event.animationName === "home-idle-plane-trip") {
      plane.classList.remove("is-flying");
      setInteractive(false);
      isAnimating = false;
      scheduleFlight();
      return;
    }
    if (event.animationName === "home-idle-plane-return") {
      plane.classList.remove("is-returning");
      resetInlineMotion();
      setInteractive(false);
      hasCrashed = false;
      isAnimating = false;
      scheduleFlight();
    }
  });

  ["pointerdown", "keydown", "scroll", "touchstart"].forEach((eventName) => {
    window.addEventListener(eventName, scheduleFlight, { passive: true });
  });
  document.addEventListener("visibilitychange", scheduleFlight);
  scheduleFlight();
})();
