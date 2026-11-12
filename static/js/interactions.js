/**
 * StudyPal - 交互反馈增强
 * 提供：按钮点击水波纹、触感反馈、加载态工具。
 * 依赖 polish.css 中的 .sp-ripple / .sp-loading 样式。
 */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function addRipple(el, ev) {
    if (reduce || !el) return;
    var rect = el.getBoundingClientRect();
    var size = Math.max(rect.width, rect.height) * 1.1;
    var x = (ev.clientX || rect.left + rect.width / 2) - rect.left;
    var y = (ev.clientY || rect.top + rect.height / 2) - rect.top;
    var span = document.createElement('span');
    span.className = 'sp-ripple';
    span.style.width = span.style.height = size + 'px';
    span.style.left = (x - size / 2) + 'px';
    span.style.top = (y - size / 2) + 'px';
    el.appendChild(span);
    span.addEventListener('animationend', function () { span.remove(); });
  }

  // 指针按下时的水波纹（仅限已定位的按钮，见 polish.css）
  document.addEventListener('pointerdown', function (e) {
    var el = e.target.closest && e.target.closest('.btn-primary, .btn-secondary, .challenge-btn-primary');
    if (el) addRipple(el, e);
  }, { passive: true });

  // 主按钮点击时的轻触感反馈（支持的设备上）
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('.btn-primary, .challenge-btn-primary');
    if (el && navigator.vibrate) { try { navigator.vibrate(8); } catch (_) {} }
  });

  // 对外工具：按钮加载态（转圈 + 禁用）
  window.spSetLoading = function (btn, on) {
    if (!btn) return;
    btn.classList.toggle('sp-loading', !!on);
    btn.disabled = !!on;
  };
})();
