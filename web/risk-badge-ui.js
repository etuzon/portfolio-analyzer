/* Shared, read-only explanations for mouse, keyboard and touch. */
(() => {
  let source = null;
  let pinned = false;
  let hideTimer;
  const panel = () => document.getElementById("riskBadgeExplanation");
  const badge = (target) => target?.closest?.("[data-risk-explanation], [data-explanation]");
  function hide() {
    clearTimeout(hideTimer);
    if (panel()) panel().hidden = true;
    source = null;
    pinned = false;
  }
  function position() {
    const popup = panel();
    if (!popup || popup.hidden || !source?.isConnected) return;
    const rect = source.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > innerHeight) { hide(); return; }
    const viewportWidth = document.documentElement?.clientWidth || innerWidth;
    popup.style.maxWidth = `${Math.max(0, viewportWidth - 24)}px`;
    const belowSpace = Math.max(0, innerHeight - rect.bottom - 20);
    const aboveSpace = Math.max(0, rect.top - 20);
    // Keep the score exposed so a second tap can close the explanation.
    popup.style.maxHeight = `${Math.min(460, Math.max(belowSpace, aboveSpace))}px`;
    const width = popup.getBoundingClientRect().width;
    const height = popup.getBoundingClientRect().height;
    const left = Math.max(12, Math.min(rect.left, viewportWidth - width - 12));
    const below = rect.bottom + 8;
    const top = height <= belowSpace || belowSpace >= aboveSpace ? below : Math.max(12, rect.top - height - 8);
    popup.style.left = `${left}px`;
    popup.style.top = `${top}px`;
  }
  function show(control) {
    clearTimeout(hideTimer);
    const popup = panel();
    if (!popup || !control) return;
    const content = control.dataset.explanation ?? control.dataset.riskExplanation;
    const changed = source !== control || popup.textContent !== content;
    if (source !== control) pinned = false;
    source = control;
    if (changed) {
      popup.textContent = content;
    }
    popup.hidden = false;
    position();
    if (changed) popup.scrollTop = 0;
  }
  document.addEventListener("pointerover", (event) => {
    if (event.pointerType === "touch" || pinned) return;
    if (panel()?.contains(event.target)) { clearTimeout(hideTimer); return; }
    const control = badge(event.target);
    if (control) show(control);
  });
  document.addEventListener("pointerout", (event) => {
    if (pinned || !source || source === document.activeElement) return;
    if (source.contains(event.relatedTarget) || panel()?.contains(event.relatedTarget)) return;
    if (source.contains(event.target) || panel()?.contains(event.target)) {
      clearTimeout(hideTimer);
      hideTimer = setTimeout(() => { if (!pinned && source !== document.activeElement) hide(); }, 150);
    }
  });
  document.addEventListener("focusin", (event) => {
    const control = badge(event.target);
    if (control) show(control);
    else if (!pinned) hide();
  });
  document.addEventListener("focusout", (event) => {
    if (!pinned && source?.contains(event.target) && !source.contains(event.relatedTarget)) hide();
  });
  document.addEventListener("click", (event) => {
    const control = badge(event.target);
    if (control) {
      if (source === control && pinned) hide();
      else { show(control); pinned = true; }
      return;
    }
    if (!panel()?.contains(event.target)) hide();
  });
  document.addEventListener("keydown", (event) => {
    const popup = panel();
    if (source && !popup?.hidden && document.activeElement === source && popup.scrollHeight > popup.clientHeight) {
      const step = Math.max(40, popup.clientHeight - 40);
      const targets = { ArrowDown: popup.scrollTop + 40, ArrowUp: popup.scrollTop - 40,
        PageDown: popup.scrollTop + step, PageUp: popup.scrollTop - step, Home: 0, End: popup.scrollHeight - popup.clientHeight };
      if (Object.hasOwn(targets, event.key)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        popup.scrollTop = Math.max(0, Math.min(targets[event.key], popup.scrollHeight - popup.clientHeight));
        return;
      }
    }
    if (event.key === "Escape" && source && !panel()?.hidden) {
      event.preventDefault();
      event.stopImmediatePropagation();
      hide();
    }
  }, true);
  window.addEventListener("resize", position);
  document.addEventListener("scroll", position, true);
  new MutationObserver((mutations) => {
    if (source && !source.isConnected) { hide(); return; }
    if (source && !panel()?.hidden && mutations.some((mutation) => mutation.type === "attributes" && mutation.target === source)) {
      const scrollTop = panel().scrollTop;
      show(source);
      panel().scrollTop = Math.min(scrollTop, Math.max(0, panel().scrollHeight - panel().clientHeight));
    }
  }).observe(document.body, { childList: true, subtree: true, attributes: true,
    attributeFilter: ["data-explanation", "data-risk-explanation"] });
})();
