/*
 * polish.js - بيخلي اللوحة تضيء تحت الماوس.
 *
 * بيسمع حركة الماوس مرة واحدة على مستوى الصفحة كلها (مش listener لكل
 * لوحة)، وبيحدّث متغيرين CSS على اللوحة اللي الماوس فوقها بس.
 * التحديث بيحصل جوه requestAnimationFrame عشان مايتنفذش أكتر من مرة
 * في الإطار الواحد مهما تحركت الماوس بسرعة - ده اللي بيمنعه إنه
 * يبطّئ الشارتات.
 */
(function () {
  "use strict";
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  var SELECTOR = ".panel, .drill, .mkt-card, .chat-panel";
  var pending = null;
  var lastEl = null;

  function apply() {
    pending = null;
    if (!lastEl) return;
    var r = lastEl.el.getBoundingClientRect();
    lastEl.el.style.setProperty("--mx", (lastEl.x - r.left) + "px");
    lastEl.el.style.setProperty("--my", (lastEl.y - r.top) + "px");
  }

  document.addEventListener("mousemove", function (e) {
    var el = e.target.closest ? e.target.closest(SELECTOR) : null;
    if (!el) return;
    lastEl = { el: el, x: e.clientX, y: e.clientY };
    if (pending === null) pending = requestAnimationFrame(apply);
  }, { passive: true });
})();
