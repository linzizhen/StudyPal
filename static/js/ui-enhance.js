/* StudyPal UI 增强 v3 —— 番茄时长预设、数据统计环形目标、设置持久化
   加载于 dashboard.js 之后，仅做渐进增强，不改变后端逻辑。 */
(function () {
  var CIRC = 326.7; /* 2 * PI * 52 */

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function setText(id, v) {
    var el = document.getElementById(id);
    if (el && v !== undefined && v !== null) el.textContent = v;
  }

  function getTargets() {
    var t = { hours: 2, week: 14, pomo: 6, duration: 25 };
    try {
      var s = JSON.parse(localStorage.getItem('sp_settings') || '{}');
      if (s.hoursTarget) t.hours = Number(s.hoursTarget) || t.hours;
      if (s.pomoTarget) t.pomo = Number(s.pomoTarget) || t.pomo;
      if (s.pomoDuration) t.duration = Number(s.pomoDuration) || t.duration;
    } catch (e) {}
    t.week = t.hours * 7;
    return t;
  }

  function gauge(id, pct, pctText, sub) {
    pct = Math.max(0, Math.min(100, Number(pct) || 0));
    var fill = document.getElementById('g-' + id + '-fill');
    if (fill) fill.style.strokeDashoffset = (CIRC * (1 - pct / 100)).toFixed(1);
    setText('g-' + id + '-pct', pctText);
    setText('g-' + id + '-sub', sub);
  }

  ready(function () {
    /* ---------- 番茄时长预设 ---------- */
    var durationInput = document.getElementById('pomo-duration-input');
    var chips = document.querySelectorAll('.pomo-chip');
    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        var d = chip.dataset.duration;
        if (durationInput) {
          durationInput.value = d;
          durationInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
        chips.forEach(function (c) { c.classList.remove('active'); });
        chip.classList.add('active');
      });
    });
    if (durationInput) {
      durationInput.addEventListener('input', function () {
        chips.forEach(function (c) {
          c.classList.toggle('active', c.dataset.duration === durationInput.value);
        });
      });
    }

    /* ---------- 设置项持久化（localStorage） ---------- */
    var hEl = document.getElementById('settings-hours-target');
    var pEl = document.getElementById('settings-pomo-target');
    var dEl = document.getElementById('settings-pomo-duration');
    var t = getTargets();
    if (hEl) hEl.value = t.hours;
    if (pEl) pEl.value = t.pomo;
    if (dEl) dEl.value = String(t.duration);
    var saveBtn = document.getElementById('btn-save-settings');
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var s = {
          hoursTarget: Number((hEl || {}).value) || 2,
          pomoTarget: Number((pEl || {}).value) || 6,
          pomoDuration: Number((dEl || {}).value) || 25
        };
        try { localStorage.setItem('sp_settings', JSON.stringify(s)); } catch (e) {}
        renderStudyGauges(studyStats, getTargets());
      });
    }

    /* ---------- 用真实数据填充数字卡与环形目标 ---------- */
    var studyStats = {};

    function renderStudyGauges(s, t) {
      s = s || {};
      var today = Number(s.today_hours) || 0;
      var week = Number(s.week_hours) || 0;
      var tp = Math.round(Math.min(100, (today / (t.hours || 2)) * 100));
      gauge('today', tp, tp + '%', today.toFixed(1) + ' / ' + t.hours + ' h');
      var wp = Math.round(Math.min(100, (week / (t.week || 14)) * 100));
      gauge('week', wp, wp + '%', week.toFixed(1) + ' / ' + t.week + ' h');
    }

    fetch('/api/study/stats')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        var s = (data && data.stats) || {};
        studyStats = s;
        setText('stats-hours', s.week_hours != null ? Number(s.week_hours).toFixed(1) : null);
        setText('stats-streak', s.streak_days);
        setText('stats-total-pomo', s.total_sessions);
        setText('pomo-stat-count', s.total_sessions);
        setText('pomo-stat-min', s.total_minutes);
        setText('pomo-stat-streak', s.streak_days);
        renderStudyGauges(s, getTargets());
      })
      .catch(function () {});

    fetch('/api/tasks/stats')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        var st = (d && d.stats) || {};
        var rate = Number(st.completion_rate) || 0;
        setText('stats-completion', Math.round(rate) + '%');
        gauge('task', rate, Math.round(rate) + '%', (st.completed || 0) + ' / ' + (st.total || 0) + ' 项');
      })
      .catch(function () {});

    fetch('/api/insights/insight-summary')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        var info = (d && d.data) || {};
        if (info.trend_text) setText('stats-trend-text', '较上周：' + info.trend_text);
      })
      .catch(function () {});
  });
})();
