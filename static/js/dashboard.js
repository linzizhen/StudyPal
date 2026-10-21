/**
 * StudyPal - Dashboard JavaScript
 */

// ============================================================
// 全局 Token 工具 + fetch 拦截（401 自动跳登录）
// ============================================================
function getToken() {
  try {
    return localStorage.getItem('token') || sessionStorage.getItem('token') || '';
  } catch (e) {
    return '';
  }
}

function getUsername() {
  try {
    return localStorage.getItem('username') || sessionStorage.getItem('username') || '';
  } catch (e) {
    return '';
  }
}

function clearAuth() {
  try {
    localStorage.removeItem('token');
    localStorage.removeItem('username');
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('username');
  } catch (e) {}
}

(function patchFetch() {
  if (window.__SP_FETCH_PATCHED__) return;
  window.__SP_FETCH_PATCHED__ = true;
  var original = window.fetch ? window.fetch.bind(window) : null;
  if (!original) return;
  // 暴露原生 fetch，供需要"绕过 401 拦截"的特定场景（如保存配置）使用
  window.__SP_ORIGINAL_FETCH__ = original;

  // 仅在已登录（有 token 缓存）时才拦截 401 自动跳转
  // 避免未登录用户的 API 请求被无限循环跳登录页
  window.fetch = function() {
    var args = Array.prototype.slice.call(arguments);
    return original.apply(window, args).then(function(resp) {
      if (resp.status === 401 && getToken()) {
        clearAuth();
        if (typeof showToast === 'function') {
          showToast('登录已过期，请重新登录', 'warning');
        }
        setTimeout(function() {
          window.location.href = '/login';
        }, 1500);
      }
      return resp;
    });
  };
})();

document.addEventListener('DOMContentLoaded', function() {
  initNavigation();
  initSearch();
  initPomodoro();
  initTasks();
  initDiary();
  initChat();
  initSettings();
  initMemory();
  updateGreeting();
  loadUserName();
  loadGrowth();
  loadCaring();
});

// 把昵称填充到侧栏与问候语
function applyUserName(name) {
  if (!name) return;
  setText('sidebar-user-name', name);
  updateGreeting();
}

// ============================================================
// 搭子的主动关心
// ============================================================
// 关心事件由后端按冷却规则产生（早安、学习提醒、情绪关怀、成就庆祝等）。
// 此前前端从不调用该接口，搭子的"主动关心"孩子在界面上看不到。
function loadCaring() {
  fetch('/api/buddy/caring')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      renderCaring((data && data.events) || []);
    })
    .catch(function() { renderCaring([]); });
}

function renderCaring(events) {
  var card = document.getElementById('caring-card');
  var box = document.getElementById('caring-messages');
  if (!card || !box) return;

  if (!events.length) {
    // 没有关心事件时不占版面
    card.style.display = 'none';
    box.innerHTML = '';
    return;
  }

  // 高优先级排在前面，最多显示 3 条，避免刷屏
  var order = { high: 0, normal: 1, low: 2 };
  var sorted = events.slice().sort(function(a, b) {
    return (order[a.priority] === undefined ? 1 : order[a.priority])
         - (order[b.priority] === undefined ? 1 : order[b.priority]);
  });

  box.innerHTML = sorted.slice(0, 3).map(function(e) {
    var safe = String(e.message || '').replace(/[<>&]/g, function(ch) {
      return { '<': '&lt;', '>': '&gt;', '&': '&amp;' }[ch];
    });
    return '<div class="caring-item">' + safe + '</div>';
  }).join('');
  card.style.display = 'block';
}

// ============================================================
// 搭子的记忆本
// ============================================================
// 记忆写入已在对话链路打通（见 routes/buddy.py 的 _remember_from_chat），
// 这里把它可视化，让孩子看得到"搭子记住了我什么"。
function loadMemory(topic) {
  var url = '/api/buddy/memory';
  if (topic) url += '?topic=' + encodeURIComponent(topic);

  return fetch(url)
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (!data) {
        renderMemoryList([]);
        return;
      }
      if (data.type === 'search') {
        // 搜索返回包装结构：{ data: {...场景}, score, matched_fields }
        var items = (data.memories || []).map(function(hit) {
          return hit && hit.data ? hit.data : null;
        }).filter(Boolean);
        renderMemoryList(items);
        return;
      }
      updateMemoryStats(data.stats || {});
      renderMemoryList(data.recent_scenes || []);
    })
    .catch(function() { renderMemoryList([]); });
}

function updateMemoryStats(stats) {
  setText('memory-count-scenes', stats.scenes || 0);
  setText('memory-count-notes', stats.profile_notes || 0);
  setText('memory-count-convs', stats.conversations || 0);
}

var MEMORY_TYPE_LABEL = {
  conversation: '聊天',
  emotion: '心情',
  milestone: '大事',
  struggle: '加油',
  achievement: '成就'
};

function renderMemoryList(items) {
  var box = document.getElementById('memory-list');
  if (!box) return;

  if (!items.length) {
    box.innerHTML = '<div class="empty-state">还没找到相关的记忆</div>';
    return;
  }

  box.innerHTML = items.map(function(m) {
    var data = m.data || m;
    var summary = escapeHtml(data.summary || '（没有摘要）');
    var date = escapeHtml(data.date || '');
    var kind = data.type || 'conversation';
    var label = MEMORY_TYPE_LABEL[kind] || '记忆';
    var tags = (data.tags || []).slice(0, 4).map(function(t) {
      return '<span class="tag">' + escapeHtml(String(t)) + '</span>';
    }).join('');
    var detail = data.details ? escapeHtml(String(data.details).slice(0, 80)) : '';
    return '<div class="memory-item">' +
      '<div class="memory-item-head"><span class="memory-kind">' + label +
      '</span><span class="memory-date">' + date + '</span></div>' +
      '<div class="memory-summary">' + summary + '</div>' +
      (detail ? '<div class="memory-detail">' + detail + '</div>' : '') +
      (tags ? '<div class="memory-tags">' + tags + '</div>' : '') +
      '</div>';
  }).join('');
}

function initMemory() {
  var searchBtn = document.getElementById('btn-memory-search');
  var clearBtn = document.getElementById('btn-memory-clear');
  var input = document.getElementById('memory-search');

  if (searchBtn) {
    searchBtn.addEventListener('click', function() {
      var kw = input ? input.value.trim() : '';
      loadMemory(kw || undefined);
    });
  }
  if (clearBtn) {
    clearBtn.addEventListener('click', function() {
      if (input) input.value = '';
      loadMemory();
    });
  }
  if (input) {
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        loadMemory(input.value.trim() || undefined);
      }
    });
  }

  loadMemory();
}

// ============================================================
// 我的挑战（延迟挂载）
// ============================================================
var _challengesMounted = false;

function mountChallenges() {
  if (_challengesMounted) return;
  var page = window.ChallengePage;
  var container = document.getElementById('page-challenges');
  if (!page || !container) {
    // 模块未加载或容器缺失：给出可读提示而不是静默失败
    if (container) {
      container.innerHTML = '<div class="empty-state-large">挑战模块暂时不可用，请刷新页面重试</div>';
    }
    return;
  }
  try {
    page.mount(container);
    _challengesMounted = true;
  } catch (e) {
    container.innerHTML = '<div class="empty-state-large">挑战模块加载出错，请稍后重试</div>';
  }
}

// ============================================================
// 导航切换
// ============================================================
var _lastSection = null;
function initNavigation() {
  var navItems = document.querySelectorAll('.nav-item');
  var sections = document.querySelectorAll('.page-section');

  function switchSection(sectionName) {
    // 离开学习搭子 → 保存当前对话
    if (_lastSection === 'buddy' && sectionName !== 'buddy') {
      if (typeof saveConversationToServer === 'function') saveConversationToServer();
    }

    navItems.forEach(function(n) { n.classList.remove('active'); });
    navItems.forEach(function(n) {
      if (n.dataset.section === sectionName) n.classList.add('active');
    });

    sections.forEach(function(s) {
      s.style.display = 'none';
      s.classList.add('hidden');
    });
    var target = document.getElementById('section-' + sectionName);
    if (target) {
      target.style.display = 'block';
      target.classList.remove('hidden');
    }

    // 进入学习搭子 → 恢复对话 + 拉历史
    if (sectionName === 'buddy') {
      if (typeof loadCurrentBuddyMessages === 'function') loadCurrentBuddyMessages();
      if (typeof loadConversationHistory === 'function') loadConversationHistory();
    }

    // 进入我的挑战 → 挂载挑战模块（延迟到首次进入，避免无谓请求）
    if (sectionName === 'challenges') {
      mountChallenges();
    }

    // 进入记忆本 → 刷新记忆（每次进入都拉最新，便于看到刚聊到的内容）
    if (sectionName === 'memory') {
      loadMemory();
    }

    // 进入任务页 / 日记页 → 用服务端数据刷新
    if (sectionName === 'tasks') {
      loadTasks();
    }
    if (sectionName === 'diary') {
      loadDiary();
    }

    updateRightSidebar(sectionName);
    _lastSection = sectionName;
  }
  window.__switchSection = switchSection;

  navItems.forEach(function(item) {
    item.addEventListener('click', function(e) {
      e.preventDefault();
      switchSection(item.dataset.section);
    });
  });

  document.querySelectorAll('.quick-card').forEach(function(card) {
    card.addEventListener('click', function(e) {
      e.preventDefault();
      var sec = card.dataset.section;
      if (sec) switchSection(sec);
    });
  });

  switchSection('dashboard');
}

function updateRightSidebar(section) {
  var rsDefault = document.getElementById('rs-default');
  var rsGrowth = document.getElementById('rs-growth');
  if (rsDefault && rsGrowth) {
    rsDefault.classList.toggle('hidden', section === 'growth');
    rsGrowth.classList.toggle('hidden', section !== 'growth');
  }
}

// ============================================================
// 问候语 + 我的成长
// ============================================================
function updateGreeting() {
  var el = document.getElementById('greeting-text');
  if (!el) return;
  var h = new Date().getHours();
  var greeting = '你好';
  if (h < 6) greeting = '还没睡呀';
  else if (h < 9) greeting = '早上好';
  else if (h < 12) greeting = '上午好';
  else if (h < 14) greeting = '中午好';
  else if (h < 18) greeting = '下午好';
  else if (h < 21) greeting = '晚上好';
  else greeting = '晚上好';
  var name = getDisplayName();
  el.textContent = name ? (greeting + '，' + name) : greeting;
}

// 取孩子昵称：优先已缓存的用户信息，其次 localStorage.username，最后请求 /api/auth/me
function getDisplayName() {
  var cached = '';
  try {
    var raw = localStorage.getItem('user') || sessionStorage.getItem('user');
    if (raw) {
      var u = JSON.parse(raw);
      cached = (u && (u.nickname || u.name)) || '';
    }
  } catch (e) { cached = ''; }
  if (!cached) cached = getUsername();
  return (cached || '').trim();
}

// 未登录时也能显示昵称：从后端补齐一次
function loadUserName() {
  var cached = getDisplayName();
  if (cached) {
    applyUserName(cached);
    return;
  }
  fetch('/api/auth/me')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      var u = (data && data.user) || null;
      if (u && (u.nickname || u.name)) {
        try { localStorage.setItem('user', JSON.stringify(u)); } catch (e) {}
        applyUserName(u.nickname || u.name);
      }
    })
    .catch(function() {});
}

// 我的成长：连续打卡天数 + 本周小星星
// 数据来源：/api/study/stats（真实学习数据），失败时安全降级为 0
function loadGrowth() {
  var fallback = { streak: 0, todayHours: 0, weekHours: 0 };
  fetch('/api/study/stats')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      var stats = (data && data.stats) || {};
      var streak = stats.streak_days || 0;
      var todayHours = stats.today_hours || 0;
      var weekHours = stats.week_hours || 0;
      renderGrowth({ streak: streak, todayHours: todayHours, weekHours: weekHours });
    })
    .catch(function() { renderGrowth(fallback); });
}

function renderGrowth(info) {
  var streak = info.streak || 0;
  var todayHours = info.todayHours || 0;
  var weekHours = info.weekHours || 0;

  // 本周星星：每完成 1 小时学习点亮一颗，最多 7 颗
  var stars = Math.min(7, Math.floor(weekHours));

  setText('rs-countdown-days', streak);
  setText('growth-streak', streak);
  setText('rs-week-stars', stars);
  setText('week-stars-total', '本周共 ' + stars + ' 颗');

  // 仪表盘预览卡
  setText('exam-school', streak + ' 天');
  setText('exam-major', stars + ' 颗');
  setText('exam-score', weekHours.toFixed(1) + ' 小时');

  // 星星网格
  var grid = document.getElementById('week-stars-grid');
  if (grid) {
    if (stars > 0) {
      var marks = [];
      for (var i = 0; i < stars; i++) marks.push('⭐');
      grid.textContent = marks.join(' ');
      grid.classList.remove('empty-state-large');
    } else {
      grid.textContent = '还没有点亮星星，今天开始吧';
    }
  }

  // 鼓励语
  var encourage = document.getElementById('growth-encourage');
  if (encourage) {
    if (streak >= 7) encourage.textContent = '连着来 ' + streak + ' 天啦，你真的很棒！';
    else if (streak >= 3) encourage.textContent = '已经坚持 ' + streak + ' 天啦，继续保持~';
    else if (todayHours > 0) encourage.textContent = '今天学过了，给自己点个赞吧';
    else encourage.textContent = '每天来学一点，就很了不起啦';
  }
}

function setText(id, value) {
  var el = document.getElementById(id);
  if (el) el.textContent = value;
}

// ============================================================
// 搜索
// ============================================================
function initSearch() {
  var input = document.getElementById('search-input');
  if (!input) return;
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      var q = input.value.trim();
      if (q) {
        input.value = '';
        showToast('搜索功能开发中: ' + q);
      }
    }
  });
}

// ============================================================
// 番茄钟
// ============================================================
function initPomodoro() {
  var toggleBtn = document.getElementById('btn-pomo-toggle');
  var resetBtn = document.getElementById('btn-pomo-reset');
  var timeEl = document.getElementById('pomo-time');
  var statusEl = document.getElementById('pomo-status');
  var durationInput = document.getElementById('pomo-duration-input');
  var durationText = document.getElementById('pomo-duration-text');
  var ringFill = document.getElementById('pomo-ring-fill');

  if (!toggleBtn) return;

  var totalSeconds = 25 * 60;
  var remaining = totalSeconds;
  var timer = null;
  var running = false;
  var circumference = 2 * Math.PI * 90;

  function formatTime(s) {
    var m = Math.floor(s / 60).toString().padStart(2, '0');
    var sec = (s % 60).toString().padStart(2, '0');
    return m + ':' + sec;
  }

  function updateRing() {
    if (!ringFill) return;
    var offset = circumference * (1 - remaining / totalSeconds);
    ringFill.style.strokeDashoffset = offset;
  }

  function tick() {
    remaining--;
    if (timeEl) timeEl.textContent = formatTime(remaining);
    updateRing();
    if (remaining <= 0) {
      clearInterval(timer);
      running = false;
      if (statusEl) statusEl.textContent = '完成！';
      if (toggleBtn) toggleBtn.textContent = '开始';
      showToast('番茄完成！休息一下吧~');
    }
  }

  toggleBtn.addEventListener('click', function() {
    if (!running) {
      if (remaining <= 0) remaining = totalSeconds;
      running = true;
      if (statusEl) statusEl.textContent = '专注中…';
      if (toggleBtn) toggleBtn.textContent = '暂停';
      timer = setInterval(tick, 1000);
    } else {
      running = false;
      clearInterval(timer);
      if (statusEl) statusEl.textContent = '已暂停';
      if (toggleBtn) toggleBtn.textContent = '继续';
    }
  });

  if (resetBtn) {
    resetBtn.addEventListener('click', function() {
      running = false;
      clearInterval(timer);
      remaining = totalSeconds;
      if (timeEl) timeEl.textContent = formatTime(remaining);
      if (statusEl) statusEl.textContent = '准备开始';
      if (toggleBtn) toggleBtn.textContent = '开始';
      updateRing();
    });
  }

  if (durationInput) {
    durationInput.addEventListener('input', function() {
      totalSeconds = parseInt(durationInput.value, 10) * 60;
      remaining = totalSeconds;
      if (!running && timeEl) timeEl.textContent = formatTime(remaining);
      if (durationText) durationText.textContent = durationInput.value;
      updateRing();
    });
  }
}

// ============================================================
// 待办任务
// ============================================================
// 任务数据以服务端为准；本地只保留一份镜像用于渲染
var _tasksCache = [];
var _tasksFilter = 'all';

function loadTasks() {
  return fetch('/api/tasks?status=all')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      _tasksCache = (data && data.tasks) || [];
      renderTasks();
    })
    .catch(function() {
      // 后端不可用时给出提示，但不清空已有列表
      var list = document.getElementById('task-list');
      if (list && !_tasksCache.length) {
        list.innerHTML = '<div class="empty-state">任务加载失败，请稍后重试</div>';
      }
    });
}

function renderTasks() {
  var list = document.getElementById('task-list');
  if (!list) return;

  var filtered = _tasksCache.filter(function(t) {
    var done = t.status === 'completed';
    if (_tasksFilter === 'pending') return !done;
    if (_tasksFilter === 'completed') return done;
    return true;
  });

  if (!filtered.length) {
    list.innerHTML = '<div class="empty-state">暂无任务</div>';
    updateTaskCounts();
    return;
  }

  list.innerHTML = filtered.map(function(t) {
    var done = t.status === 'completed';
    return '<div class="task-item' + (done ? ' completed' : '') + '" data-id="' +
      escapeHtml(String(t.id)) + '">' +
      '<div class="task-checkbox' + (done ? ' checked' : '') + '"></div>' +
      '<span class="task-text">' + escapeHtml(t.title || '') + '</span>' +
      '<button class="task-delete">&times;</button></div>';
  }).join('');

  list.querySelectorAll('.task-checkbox').forEach(function(cb) {
    cb.addEventListener('click', function() {
      var el = cb.closest('.task-item');
      var id = el && el.dataset.id;
      if (id) completeTask(id);
    });
  });

  list.querySelectorAll('.task-delete').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var el = btn.closest('.task-item');
      var id = el && el.dataset.id;
      if (id) deleteTask(id);
    });
  });

  updateTaskCounts();
}

function updateTaskCounts() {
  var pending = _tasksCache.filter(function(t) { return t.status !== 'completed'; }).length;
  var completed = _tasksCache.filter(function(t) { return t.status === 'completed'; }).length;
  setText('tasks-pending-count', pending + ' 待完成');
  setText('tasks-completed-count', completed + ' 已完成');
}

function createTask(title) {
  var value = (title || '').trim();
  if (!value) {
    showToast('请先填写任务内容');
    return Promise.resolve();
  }
  return fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: value })
  })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (data && data.success) {
        showToast('任务已添加');
        return loadTasks();
      }
      showToast((data && data.error) || '添加失败');
    })
    .catch(function() { showToast('网络异常，任务未保存'); });
}

function completeTask(id) {
  return fetch('/api/tasks/' + encodeURIComponent(id) + '/complete', { method: 'POST' })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (data && data.success) {
        if (data.new_achievements && data.new_achievements.length) {
          showToast('完成啦！解锁了新成就 🎉');
        }
        return loadTasks();
      }
      showToast((data && data.error) || '操作失败');
    })
    .catch(function() { showToast('网络异常，状态未保存'); });
}

function deleteTask(id) {
  return fetch('/api/tasks/' + encodeURIComponent(id), { method: 'DELETE' })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (data && data.success) {
        showToast('已删除');
        return loadTasks();
      }
      showToast('删除失败');
    })
    .catch(function() { showToast('网络异常，未删除'); });
}

function initTasks() {
  var input = document.getElementById('new-task-input');
  var addBtn = document.getElementById('btn-add-task');
  var list = document.getElementById('task-list');
  var tabs = document.querySelectorAll('.filter-tab');

  if (!list) return;

  if (addBtn) {
    addBtn.addEventListener('click', function() {
      createTask(input ? input.value : '').then(function() {
        if (input) input.value = '';
      });
    });
  }
  if (input) {
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        createTask(input.value).then(function() { input.value = ''; });
      }
    });
  }

  tabs.forEach(function(tab) {
    tab.addEventListener('click', function() {
      tabs.forEach(function(t) { t.classList.remove('active'); });
      tab.classList.add('active');
      _tasksFilter = tab.dataset.filter || 'all';
      renderTasks();
    });
  });

  // 从服务端加载真实任务
  loadTasks();
}

// ============================================================
// 学习日记（数据以服务端为准）
// ============================================================
var _diaryEntries = [];
var _currentMoodLevel = 5;   // 默认"愉快"档，对应后端 10 档量表

function loadDiary() {
  return fetch('/api/diary?limit=20')
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      _diaryEntries = (data && data.entries) || [];
      renderDiaryList();
    })
    .catch(function() {});

  function renderDiaryList() {
    var box = document.getElementById('diary-list');
    if (!box) return;
    if (!_diaryEntries.length) {
      box.innerHTML = '<div class="empty-state">还没有日记，写下今天的心情吧</div>';
      return;
    }
    box.innerHTML = _diaryEntries.map(function(e) {
      var id = escapeHtml(String(e.id));
      var label = escapeHtml(e.emotion_label || '');
      var date = escapeHtml(e.date || '');
      var text = escapeHtml(e.biggest_event || e.study_feeling || '');
      return '<div class="diary-item" data-id="' + id + '">' +
        '<div class="diary-item-head"><span class="diary-date">' + date +
        '</span><span class="diary-mood">' + label + '</span></div>' +
        '<div class="diary-item-text">' + text + '</div>' +
        '<button class="diary-delete" title="删除">&times;</button></div>';
    }).join('');

    box.querySelectorAll('.diary-delete').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var el = btn.closest('.diary-item');
        if (el && el.dataset.id) deleteDiary(el.dataset.id);
      });
    });
  }
}

function saveDiary() {
  var titleEl = document.getElementById('diary-title');
  var contentEl = document.getElementById('diary-content');
  var eventEl = document.getElementById('diary-biggest-event');
  var wordsEl = document.getElementById('diary-words-to-buddy');

  var content = contentEl ? contentEl.textContent.trim() : '';
  var title = titleEl ? titleEl.value.trim() : '';
  var event = eventEl ? eventEl.value.trim() : '';
  var words = wordsEl ? wordsEl.value.trim() : '';

  if (!content && !title && !event) {
    showToast('写点什么再保存吧');
    return Promise.resolve();
  }

  var payload = {
    emotion_level: _currentMoodLevel,
    study_feeling: title,
    biggest_event: event || content || title,
    words_to_buddy: words
  };

  return fetch('/api/diary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (data && data.success) {
        showToast(data.buddy_caring ? '日记已保存，搭子有话对你说' : '日记已保存');
        if (titleEl) titleEl.value = '';
        if (contentEl) contentEl.textContent = '';
        if (eventEl) eventEl.value = '';
        if (wordsEl) wordsEl.value = '';
        setText('diary-word-count', '0 字');
        return loadDiary();
      }
      showToast((data && data.error) || '保存失败');
    })
    .catch(function() { showToast('网络异常，日记未保存'); });
}

function deleteDiary(id) {
  return fetch('/api/diary/' + encodeURIComponent(id), { method: 'DELETE' })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (data && data.success) {
        showToast('已删除');
        return loadDiary();
      }
      showToast('删除失败');
    })
    .catch(function() { showToast('网络异常，未删除'); });
}

function initDiary() {
  var saveBtn = document.getElementById('btn-save-diary');
  var contentEl = document.getElementById('diary-content');
  var wordCountEl = document.getElementById('diary-word-count');
  var tagInput = document.getElementById('tag-input');
  var tagList = document.getElementById('tag-list');
  var moodBtns = document.querySelectorAll('.mood-btn');

  if (saveBtn) {
    saveBtn.addEventListener('click', function() { saveDiary(); });
  }

  if (contentEl) {
    contentEl.addEventListener('input', function() {
      if (wordCountEl) wordCountEl.textContent = contentEl.textContent.length + ' 字';
    });
  }

  if (tagInput) {
    tagInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var val = tagInput.value.trim();
        if (val) {
          addTag(val);
          tagInput.value = '';
        }
      }
    });
  }

  function addTag(text) {
    if (!tagList) return;
    var chip = document.createElement('span');
    chip.className = 'tag-chip';
    chip.innerHTML = escapeHtml(text) +
      ' <button type="button" class="tag-remove" aria-label="删除标签 ' + escapeHtml(text) + '">&times;</button>';
    tagList.appendChild(chip);
    var rm = chip.querySelector('.tag-remove');
    if (rm) rm.addEventListener('click', function() { chip.remove(); });
  }

  // 情绪按钮：读 data-level 并记为待提交的情绪档位
  moodBtns.forEach(function(btn) {
    btn.addEventListener('click', function() {
      moodBtns.forEach(function(b) { b.classList.remove('selected'); });
      btn.classList.add('selected');
      var level = parseInt(btn.dataset.level, 10);
      if (!isNaN(level)) _currentMoodLevel = level;
    });
  });

  // 默认选中中位档
  if (moodBtns.length) {
    var selected = document.querySelector('.mood-btn.selected');
    if (!selected) {
      var mid = moodBtns[Math.floor(moodBtns.length / 2)];
      mid.classList.add('selected');
      var lv = parseInt(mid.dataset.level, 10);
      if (!isNaN(lv)) _currentMoodLevel = lv;
    }
  }

  loadDiary();
}

// ============================================================
// 学习搭子
// ============================================================
// 角色数据表：必须覆盖后端 BUDDY_ROLES 的全部 6 个角色。
// xuejie 是后端已兼容的别名（等价 senior），此处保留以兼容既有 HTML。
const BUDDY_DATA = {
  xiaodou: { name: "小豆",  type: "温柔陪伴型", emoji: "🌸", bg: "#FFD93D", personality: "warm" },
  aran:    { name: "阿燃",  type: "热血激励型", emoji: "⚡", bg: "#FF6B6B", personality: "passionate" },
  xuejie:  { name: "小老师", type: "耐心讲解型", emoji: "📚", bg: "#74C0FC", personality: "rational" },
  senior:  { name: "小老师", type: "耐心讲解型", emoji: "📚", bg: "#74C0FC", personality: "rational" },
  xiaoye:  { name: "小夜",  type: "安静倾听型", emoji: "🌙", bg: "#9775FA", personality: "listener" },
  xj:      { name: "戏精",  type: "幽默搞怪型", emoji: "🎭", bg: "#FFD93D", personality: "playful" },
  azheng:  { name: "阿正",  type: "理性分析型", emoji: "🤖", bg: "#6C7A89", personality: "logical" }
};

let currentBuddy = "xiaodou";

function initChat() {
  const input = document.getElementById("buddy-input");
  const sendBtn = document.getElementById("btn-send-message");
  const messages = document.getElementById("buddy-messages");
  const quickReplies = document.querySelectorAll(".quick-prompt-btn");
  const newChatBtn = document.getElementById("btn-new-chat");

  if (!messages) return;

  function renderWelcome(buddyId) {
    const buddy = BUDDY_DATA[buddyId];
    messages.innerHTML = `
      <div class="message message-buddy">
        <div class="message-avatar-emoji" style="background:${buddy.bg}">${buddy.emoji}</div>
        <div class="message-content">
          <div class="message-author">${buddy.name}</div>
          <div class="message-bubble">嗨！我是${buddy.name}，你的学习搭子~ 🌟 有什么想聊的吗？</div>
          <div class="message-time">现在</div>
        </div>
      </div>
    `;
  }

  function switchBuddy(buddyId) {
    currentBuddy = buddyId;
    const buddy = BUDDY_DATA[buddyId];
    const typeShort = { warm: '温柔', passionate: '热血', rational: '学霸', listener: '倾听', humor: '幽默', analyst: '导师' };
    const short = typeShort[buddy.personality] || buddy.type.replace('型', '');

    // 聊天区头部
    const hAvatar = document.getElementById('chat-buddy-avatar');
    const hName = document.getElementById('chat-buddy-name');
    const hStatus = document.getElementById('chat-buddy-status');
    if (hAvatar) { hAvatar.textContent = buddy.emoji; hAvatar.style.background = buddy.bg; }
    if (hName) hName.textContent = buddy.name;
    if (hStatus) hStatus.textContent = '在线';
  var hType = document.getElementById('chat-buddy-type');
  if (hType) hType.textContent = buddy.type;

    // 右侧搭子档案
    const pAvatar = document.getElementById('profile-avatar');
    const pName = document.getElementById('profile-name');
    const pType = document.getElementById('profile-type');
    if (pAvatar) { pAvatar.textContent = buddy.emoji; pAvatar.style.background = buddy.bg; }
    if (pName) pName.textContent = buddy.name;
    if (pType) pType.textContent = buddy.type;

    // 右侧搭子列表 active
    document.querySelectorAll('.roster-item').forEach(item => {
      item.classList.toggle('active', item.dataset.buddy === buddyId);
    });

    // 左侧对话列表 active
    document.querySelectorAll('.conversation-item').forEach(item => {
      item.classList.toggle('active', item.querySelector('.conversation-name').textContent === buddy.name);
    });

    renderWelcome(buddyId);
  }

  function addMessage(text, sender) {
    const buddy = BUDDY_DATA[currentBuddy];
    const now = new Date();
    const timeStr = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
    const div = document.createElement("div");
    div.className = "message " + (sender === "user" ? "message-user" : "message-buddy");

    if (sender === "buddy") {
      div.innerHTML = `
        <div class="message-avatar-emoji" style="background:${buddy.bg}">${buddy.emoji}</div>
        <div class="message-content">
          <div class="message-author">${buddy.name}</div>
          <div class="message-bubble">${formatChatText(text)}</div>
          <div class="message-time">${timeStr}</div>
        </div>
      `;
    } else {
      div.innerHTML = `
        <div class="message-content">
          <div class="message-bubble">${escapeHtml(text)}</div>
          <div class="message-time">${timeStr}</div>
        </div>
      `;
    }

    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  // AI 加载气泡（3 个跳动圆点 + 搭子专属思考文字）
  function addLoadingBubble() {
    const buddy = BUDDY_DATA[currentBuddy];
    const loadingTexts = {
      warm: '小豆正在思考…',
      passionate: '阿燃正在燃烧斗志…',
      rational: '小老师正在一步步推导…',
      listener: '小夜正在静静思考…',
      xuejie: '小老师正在一步步推导…',
      xiaodou: '小豆正在思考…',
      aran: '阿燃正在燃烧斗志…',
      senior: '小老师正在一步步推导…',
      xiaoye: '小夜正在静静思考…'
    };
    const text = loadingTexts[currentBuddy] || '搭子正在思考…';
    const id = 'loading-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'message message-buddy';
    div.innerHTML =
      '<div class="message-avatar-emoji" style="background:' + buddy.bg + '">' + buddy.emoji + '</div>' +
      '<div class="message-content">' +
        '<div class="message-author">' + buddy.name + '</div>' +
        '<div class="message-bubble" style="display:flex;align-items:center;gap:8px;">' +
          '<span class="loading-dots" style="display:inline-flex;gap:4px;">' +
            '<span style="width:8px;height:8px;background:#ddd;border-radius:50%;"></span>' +
            '<span style="width:8px;height:8px;background:#ddd;border-radius:50%;"></span>' +
            '<span style="width:8px;height:8px;background:#ddd;border-radius:50%;"></span>' +
          '</span>' +
          '<span style="font-size:13px;color:#8C8C8C;">' + text + '</span>' +
        '</div>' +
      '</div>';
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return id;
  }

  function removeLoadingBubble(id) {
    var el = document.getElementById(id);
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  // 轻量 markdown 转 HTML（仅处理换行和 **加粗**）
  function formatChatText(text) {
    if (!text) return '';
    var safe = escapeHtml(text);
    safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/\n/g, '<br>');
    return safe;
  }

  // 更新对话次数
  function bumpChatStat() {
    var el = document.getElementById('stat-chats');
    if (!el) return;
    var n = parseInt(el.textContent || '0', 10) || 0;
    el.textContent = n + 1;
  }

  function sendMessage() {
    const text = (input ? input.value : "").trim();
    if (!text) return;
    if (sendBtn && sendBtn.disabled) return;

    if (sendBtn) sendBtn.disabled = true;
    addMessage(text, "user");
    if (input) input.value = "";

    // 调用真实 AI（读取用户配置的智谱模型）
    const loadingId = addLoadingBubble();

    fetch('/api/buddy/quick-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        buddy_id: currentBuddy,
        message: text,
        explain_mode: getExplainMode()
      })
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      removeLoadingBubble(loadingId);
      if (data && data.success) {
        addMessage(data.reply || '…', 'buddy');
        bumpChatStat();
      } else {
        var err = (data && data.error) || 'AI 回复失败';
        var tip = (data && data.tip) || '';
        addMessage('抱歉，暂时无法回复。' + err + (tip ? '\n💡 ' + tip : ''), 'buddy');
        if (typeof showToast === 'function') showToast(err);
      }
    })
    .catch(function(e) {
      removeLoadingBubble(loadingId);
      addMessage('网络异常，请检查 AI 配置或网络状态。', 'buddy');
      if (typeof showToast === 'function') showToast('发送失败：' + e.message);
    })
    .finally(function() {
      if (sendBtn) sendBtn.disabled = false;
    });
  }

  function getExplainMode() {
    var sel = document.querySelector('input[name="explain-mode"]:checked');
    if (!sel) return 'auto';
    // 把 UI 的 auto/game/speed 直接映射
    return sel.value || 'auto';
  }

  document.querySelectorAll(".roster-item").forEach(item => {
    item.addEventListener("click", () => {
      if (item.dataset.buddy) switchBuddy(item.dataset.buddy);
    });
  });

  if (sendBtn) sendBtn.addEventListener("click", sendMessage);
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  // 快捷 chip 按钮
  document.querySelectorAll(".quick-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      // 知识点讲解 chip 是开关入口，不走聊天
      if (chip.id === "btn-open-explain-panel") {
        openBuddyExplain();
        return;
      }
      const text = (chip.dataset.prompt || "").trim();
      if (text && input) {
        input.value = text;
        sendMessage();
      }
    });
  });

  // 右侧栏快捷功能按钮（知识点讲解 / 学习计划 / 学习方法 / 学习报告）
  // 改为展开游戏化讲解面板，而非走普通聊天
  document.querySelectorAll(".quick-action-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      var prompt = (btn.dataset.prompt || "").trim();
      var requestType = (btn.dataset.requestType || "topic").trim();

      var panel = document.getElementById("buddy-explain-section");
      var topicInput = document.getElementById("explain-topic-input");
      var startBtn = document.getElementById("btn-start-explain");

      // 展开面板
      if (panel) panel.classList.remove("hidden");
      if (topicInput) {
        topicInput.value = prompt.replace(/^(请帮我|请生成)/, "").replace(/^(讲解|制定|推荐|生成)/, "");
        topicInput.focus();
      }

      // 如果有 startBtn，说明已绑定 startExplain 逻辑
      // 按钮会读取当前 request_type（通过 hidden input），直接点它
      // 更新 requestType 供 startExplain 读取
      if (typeof _pendingRequestType !== "undefined") {
        _pendingRequestType = requestType;
      }
      // 触发一次讲解（自动从 input 取值）
      if (startBtn) {
        setTimeout(function() { startExplain(requestType); }, 50);
      }
    });
  });

  // 右侧栏「我的搭子」列表（新 .my-buddy-item 风格）切换
  document.querySelectorAll(".my-buddy-item").forEach(item => {
    item.addEventListener("click", () => {
      var bid = item.dataset.buddy;
      if (bid && typeof switchBuddy === 'function') {
        switchBuddy(bid);
        showToast('已切换到' + (BUDDY_DATA[bid] ? BUDDY_DATA[bid].name : bid));
      }
    });
  });

  // 知识点讲解功能
  initBuddyExplain();

  // 新建对话
  var newConvBtn = document.getElementById("btn-new-conversation");
  if (newConvBtn) {
    newConvBtn.addEventListener("click", () => renderWelcome(currentBuddy));
  }

  // 历史记录按钮
  var historyBtn = document.getElementById("btn-chat-history");
  if (historyBtn) {
    historyBtn.addEventListener("click", () => showToast("历史记录功能开发中…"));
  }

  // 设置页创建搭子按钮 → 打开弹窗
  var openDesignerBtn = document.getElementById("btn-open-buddy-designer-settings");
  if (openDesignerBtn) {
    openDesignerBtn.addEventListener("click", function() {
      var modal = document.getElementById("buddy-designer-modal");
      if (modal) modal.classList.remove("hidden");
    });
  }

  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => renderWelcome(currentBuddy));
  }

  document.querySelectorAll(".chat-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".chat-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      showToast(tab.dataset.tab === "history" ? "历史对话加载中…" : "当前对话");
    });
  });

  document.querySelectorAll(".buddy-list-item").forEach(item => {
    item.addEventListener("click", () => {
      const id = item.dataset.buddy;
      if (id) switchBuddy(id);
    });
  });

  // 把 send 按钮绑定到真实 AI 调用（覆盖默认 mock）
  if (sendBtn) sendBtn.onclick = sendChatMessage;
  if (input) {
    input.onkeydown = function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    };
  }

  // 「+ 新对话」按钮
  var newConvBtn = document.getElementById('btn-new-conversation');
  if (newConvBtn) newConvBtn.onclick = startNewConversation;

  // 进入页面时拉历史
  loadConversationHistory();

  switchBuddy(currentBuddy);
}

function notifyStudyTime(minutes) {
  if (!minutes) return;
  const buddy = BUDDY_DATA[currentBuddy];
  const texts = [
    `哇，${buddy.name}看到你学习了${minutes}分钟，真是勤奋呢！`,
    `你已经专注了${minutes}分钟，太棒了！`,
    `学习${minutes}分钟了，记得适当休息哦~`
  ];
  const text = texts[Math.floor(Math.random() * texts.length)];
  addMessage(text, "buddy");
}

// ============================================================
// 设置
// ============================================================
function initSettings() {
  var saveBtn = document.getElementById('btn-save-settings');
  if (saveBtn) {
    saveBtn.addEventListener('click', function() {
      showToast('设置已保存！');
    });
  }

  // 账户状态卡
  initAccountStatus();

  // 修改密码
  initChangePassword();

  // 搭子设计器弹窗
  var openBtn = document.getElementById('btn-open-buddy-designer');
  if (openBtn) {
    openBtn.addEventListener('click', function() {
      document.getElementById('buddy-designer-modal').classList.remove('hidden');
      document.getElementById('modal-title').textContent = '创建新搭子';
      document.getElementById('bd-name').value = '';
      document.getElementById('bd-desc').value = '';
      document.getElementById('bd-greeting').value = '';
      document.querySelectorAll('.avatar-option').forEach(function(o) { o.classList.remove('selected'); });
      var first = document.querySelector('.avatar-option');
      if (first) first.classList.add('selected');
    });
  }
  var closeBtn = document.getElementById('btn-close-modal');
  if (closeBtn) closeBtn.addEventListener('click', closeBuddyModal);
  var cancelBtn = document.getElementById('btn-cancel-buddy');
  if (cancelBtn) cancelBtn.addEventListener('click', closeBuddyModal);

  // 头像选择
  document.querySelectorAll('.avatar-option').forEach(function(opt) {
    opt.addEventListener('click', function() {
      document.querySelectorAll('.avatar-option').forEach(function(o) { o.classList.remove('selected'); });
      opt.classList.add('selected');
    });
  });

  // 保存搭子
  var saveBuddyBtn = document.getElementById('btn-save-buddy');
  if (saveBuddyBtn) saveBuddyBtn.addEventListener('click', saveBuddyFromModal);

  // 加载 AI 预设模型
  loadAiPresets();

  // 测试连接
  var testBtn = document.getElementById('btn-test-ai');
  if (testBtn) testBtn.addEventListener('click', testAiConnection);

  // 保存 AI 配置
  var saveAiBtn = document.getElementById('btn-save-ai');
  if (saveAiBtn) saveAiBtn.addEventListener('click', saveAiConfig);
}

function closeBuddyModal() {
  var modal = document.getElementById('buddy-designer-modal');
  if (modal) modal.classList.add('hidden');
}

function saveBuddyFromModal() {
  var name = (document.getElementById('bd-name') || {}).value || '';
  var personality = (document.getElementById('bd-personality') || {}).value || 'warm';
  var desc = (document.getElementById('bd-desc') || {}).value || '';
  var greeting = (document.getElementById('bd-greeting') || {}).value || '';
  var selected = document.querySelector('.avatar-option.selected');
  var emoji = selected ? selected.dataset.emoji : '🌸';
  var bg = selected ? selected.dataset.bg : '#F5F5F5';

  if (!name.trim()) { showToast('请输入搭子名字'); return; }

  var typeNames = { warm: '温暖陪伴型', passionate: '热血激励型', rational: '耐心讲解型', listener: '安静倾听型', humor: '幽默风趣型', analyst: '耐心讲解型' };
  var buddyId = 'custom_' + Date.now();

  var list = document.getElementById('buddy-designer-list');
  if (!list) { showToast('列表不存在'); return; }

  var item = document.createElement('div');
  item.className = 'designer-buddy-item';
  item.dataset.buddy = buddyId;
  item.innerHTML =
    '<div class="designer-buddy-avatar" style="background:' + bg + '">' + emoji + '</div>' +
    '<div class="designer-buddy-info">' +
      '<div class="designer-buddy-name">' + escapeHtml(name) + '</div>' +
      '<div class="designer-buddy-type">' + (typeNames[personality] || personality) + '</div>' +
      '<div class="designer-buddy-desc">' + escapeHtml(desc || '暂无描述') + '</div>' +
    '</div>';

  list.appendChild(item);
  closeBuddyModal();
  showToast('搭子保存成功！');
}

async function loadAiPresets() {
  var sel = document.getElementById('ai-preset-select');
  if (!sel) return;
  try {
    var res = await fetch('/api/ai-model/presets');
    var data = await res.json();
    if (!data.success || !data.presets) return;

    // 按 provider 分组
    var groups = { zhipu: [], openai: [], ollama: [], other: [] };
    data.presets.forEach(function(p) {
      var pv = (p.provider || '').toLowerCase();
      if (pv === 'zhipu') groups.zhipu.push(p);
      else if (pv === 'ollama') groups.ollama.push(p);
      else if (pv === 'openai') groups.openai.push(p);
      else groups.other.push(p);
    });

    sel.innerHTML = '<option value="">-- 选择预设模型 --</option>';

    function appendGroup(label, items) {
      if (!items.length) return;
      var og = document.createElement('optgroup');
      og.label = label;
      items.forEach(function(p) {
        var opt = document.createElement('option');
        opt.value = p.key;
        opt.textContent = p.name;
        opt.dataset.api = p.base_url || '';
        opt.dataset.model = p.model || '';
        og.appendChild(opt);
      });
      sel.appendChild(og);
    }

    appendGroup('智谱AI (Zhipu/GLM) - 国内免费推荐', groups.zhipu);
    appendGroup('云端模型 (OpenAI 兼容)', groups.openai);
    appendGroup('本地模型 (Ollama)', groups.ollama);
    appendGroup('其他', groups.other);

    // 选中预设时自动填充 base-url 和 model-name
    sel.addEventListener('change', function() {
      var opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.value) return;
      var urlEl = document.getElementById('ai-base-url');
      var modelEl = document.getElementById('ai-model-name');
      if (opt.dataset.api) urlEl.value = opt.dataset.api;
      if (opt.dataset.model) modelEl.value = opt.dataset.model;
    });

    // 加载当前用户的配置回填表单
    loadCurrentAiConfig();
  } catch(e) {}
}

async function loadCurrentAiConfig() {
  try {
    var res = await fetch('/api/ai-model/current');
    var data = await res.json();
    if (!data || !data.success) return;
    var sel = document.getElementById('ai-preset-select');
    var urlEl = document.getElementById('ai-base-url');
    var modelEl = document.getElementById('ai-model-name');
    var keyEl = document.getElementById('ai-api-key');
    if (!sel || !urlEl || !modelEl) return;

    if (data.mode === 'preset' && data.model_key) {
      sel.value = data.model_key;
      var opt = sel.options[sel.selectedIndex];
      if (opt && opt.dataset.api) urlEl.value = opt.dataset.api;
      if (opt && opt.dataset.model) modelEl.value = opt.dataset.model;
    } else if (data.mode === 'custom' && data.model) {
      sel.value = '';
      urlEl.value = data.model.base_url || '';
      modelEl.value = data.model.model || '';
      if (keyEl) keyEl.value = '';  // 密钥不回填，由用户重输
    }
  } catch(e) {}
}

async function testAiConnection() {
  var key = (document.getElementById('ai-api-key') || {}).value || '';
  var baseUrl = (document.getElementById('ai-base-url') || {}).value || '';
  var model = (document.getElementById('ai-model-name') || {}).value || '';
  // 前端做轻校验：若三个字段都空，多半是预设模式或没填，给出明确提示
  if (!baseUrl || !model) {
    showToast('请先选择预设或填写自定义模型地址/模型名');
    return;
  }
  if (!key) {
    // key 为空时仍发送请求，由后端根据已登录用户回退到保存的自定义 key
    console.log('[DEBUG] testAiConnection: api_key 为空，交给后端回退处理');
  }
  // 关键：/test 走原 fetch 绕开全局 401 拦截器，否则智谱 API 返回 401 会被当成登录失效跳页
  var rawFetch = window.__SP_ORIGINAL_FETCH__ || window.fetch.bind(window);
  var headers = { 'Content-Type': 'application/json' };
  var tk = getToken();
  if (tk) headers['Authorization'] = 'Bearer ' + tk;
  showToast('正在测试连接…');
  try {
    var res = await rawFetch('/api/ai-model/test', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({ api_key: key, base_url: baseUrl, model: model })
    });
    // 即使 status 非 2xx，response 也可能有 JSON body（后端 /test 会统一返 JSON）
    var data = null;
    try { data = await res.json(); } catch (e) { data = { success: false, error: '响应不是 JSON 格式' }; }
    if (data && data.success) {
      showToast('连接成功！');
    } else {
      // 优先显示后端提供的错误原因（"认证失败，请检查 API Key" / "连接超时" 等）
      // 而不是裸 HTTP 401，避免用户把"智谱的鉴权失败"误解为"自己的 token 失效"
      var msg = (data && data.error) ? data.error : ('HTTP ' + res.status);
      showToast('连接失败：' + msg);
    }
  } catch(e) {
    showToast('测试失败：' + (e && e.message ? e.message : '未知错误'));
  }
}

async function saveAiConfig() {
  var preset = (document.getElementById('ai-preset-select') || {}).value || '';
  var baseUrl = (document.getElementById('ai-base-url') || {}).value || '';
  var apiKey = (document.getElementById('ai-api-key') || {}).value || '';
  var modelName = (document.getElementById('ai-model-name') || {}).value || '';
  // 关键修复：保存接口必须带 Authorization 头（与 GET 不同），用原 fetch 绕开全局 401 拦截器
  var rawFetch = window.__SP_ORIGINAL_FETCH__ || window.fetch.bind(window);
  var authHeaders = { 'Content-Type': 'application/json' };
  var tk = getToken();
  if (tk) authHeaders['Authorization'] = 'Bearer ' + tk;
  showToast('正在保存…');
  try {
    if (preset) {
      var res = await rawFetch('/api/ai-model/preset', {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ model_key: preset })
      });
      var data = await res.json();
      if (data.success) { showToast('预设模型已切换'); return; }
      showToast('保存失败：' + (data.error || ('HTTP ' + res.status)));
      return;
    }
    if (baseUrl && apiKey && modelName) {
      var res = await rawFetch('/api/ai-model/custom', {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ base_url: baseUrl, api_key: apiKey, model: modelName })
      });
      var data = await res.json();
      if (data.success) { showToast('自定义模型已保存'); return; }
      // 关键：401 是登录失效，全局拦截器会清 token 跳 login；这里只显示后端给的中文原因
      showToast('保存失败：' + (data.error || ('HTTP ' + res.status)));
      return;
    }
    showToast('请填写 API 地址、密钥和模型名称');
  } catch(e) { showToast('保存失败：' + e.message); }
}

// ============================================================
// 工具函数
// ============================================================
function showToast(message) {
  var toast = document.getElementById('study-pal-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'study-pal-toast';
    toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1A1A1A;color:#fff;padding:10px 20px;border-radius:20px;font-size:13px;z-index:9999;opacity:1;transition:opacity ' + (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches ? '0.01s' : '0.3s') + ';pointer-events:none;';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.opacity = '1';
  clearTimeout(toast._timer);
  toast._timer = setTimeout(function() { toast.style.opacity = '0'; }, 2500);
}

function escapeHtml(str) {
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ============================================================
// 知识点讲解
// ============================================================

var EXPLAIN_LOADER_WORDS = {
  xiaodou: ['小豆正在浇灌知识花园…', '花瓣慢慢展开…', '为你种下一颗种子…', '风里飘来花香…'],
  aran:    ['阿燃正在点燃竞技场！', '燃烧吧小宇宙！', '准备战斗！', '能量正在汇聚…'],
  senior:  ['小老师摆好了教具…', '正在一步一步拆解…', '举个小例子…', '马上讲明白…'],
  xuejie:  ['小老师摆好了教具…', '正在一步一步拆解…', '举个小例子…', '马上讲明白…'],
  xiaoye:  ['小夜望向窗外…', '月光慢慢亮起…', '星星正在连线…', '夜风送来灵感…'],
  xj:      ['戏精正在抖段子…', '笑料加载中…', '麦克风调音完毕…', '快乐即将到达战场…'],
  azheng:  ['阿正启动数据仪表盘…', '采集样本中…', '逻辑链校验中…', '输出结论渲染中…']
};

var EXPLAIN_ROLE_THEME = {
  xiaodou: { cls: 'buddy-theme-xiaodou', emoji: '🌸' },
  aran:    { cls: 'buddy-theme-aran',    emoji: '⚡' },
  senior:  { cls: 'buddy-theme-senior',  emoji: '📚' },
  xiaoye:  { cls: 'buddy-theme-xiaoye',  emoji: '🌙' },
  xj:      { cls: 'buddy-theme-xj',      emoji: '🎭' },
  azheng:  { cls: 'buddy-theme-azheng',  emoji: '🤖' }
};

var BUDDY_THEME_CLASSES = ['buddy-theme-xiaodou','buddy-theme-aran','buddy-theme-senior','buddy-theme-xiaoye','buddy-theme-xj','buddy-theme-azheng'];

var _explainLoaderTimer = null;

function initBuddyExplain() {
  var panel = document.getElementById('buddy-explain-section');
  if (!panel) return;

  var openBtn = document.getElementById('btn-open-explain-panel');
  var closeBtn = document.getElementById('btn-close-explain');
  var startBtn = document.getElementById('btn-start-explain');
  var topicInput = document.getElementById('explain-topic-input');

  function closePanel() {
    panel.classList.add('hidden');
    stopExplainLoader();
    var lr = document.getElementById('explain-loading');
    var rr = document.getElementById('explain-result');
    if (lr) lr.classList.add('hidden');
    if (rr) rr.classList.add('hidden');
  }

  if (openBtn) {
    openBtn.addEventListener('click', function() {
      // 展开讲解区前，先把当前搭子的主题 class 同步上去
      applyBuddyTheme(currentBuddy || 'xiaodou');
      panel.classList.remove('hidden');
      _pendingRequestType = 'topic';
      if (topicInput) topicInput.focus();
    });
  }
  if (closeBtn) closeBtn.addEventListener('click', closePanel);
  if (startBtn) startBtn.addEventListener('click', function(e) { startExplain('topic'); });
  if (topicInput) {
    topicInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        startExplain();
      }
    });
  }
}

function openBuddyExplain() {
  applyBuddyTheme(currentBuddy || 'xiaodou');
  var panel = document.getElementById('buddy-explain-section');
  if (panel) panel.classList.remove('hidden');
  var topicInput = document.getElementById('explain-topic-input');
  if (topicInput) topicInput.focus();
}

function applyBuddyTheme(buddyId) {
  var theme = EXPLAIN_ROLE_THEME[buddyId] || EXPLAIN_ROLE_THEME.xiaodou;
  var loaderIcon = document.getElementById('buddy-loader-icon');
  var loaderEmoji = document.getElementById('buddy-loader-emoji');
  var section = document.getElementById('buddy-explain-section');

  if (loaderIcon) {
    BUDDY_THEME_CLASSES.forEach(function(c){ loaderIcon.classList.remove(c); });
    loaderIcon.classList.add(theme.cls);
  }
  if (loaderEmoji) loaderEmoji.textContent = theme.emoji;
  if (section) {
    BUDDY_THEME_CLASSES.forEach(function(c){ section.classList.remove(c); });
    section.classList.add(theme.cls);
  }
}

function showExplainLoading(roleId) {
  var lr = document.getElementById('explain-loading');
  var rr = document.getElementById('explain-result');
  var loaderText = document.getElementById('buddy-loader-text');
  if (lr) lr.classList.remove('hidden');
  if (rr) rr.classList.add('hidden');
  applyBuddyTheme(roleId);

  var words = EXPLAIN_LOADER_WORDS[roleId] || EXPLAIN_LOADER_WORDS.xiaodou;
  var idx = 0;
  if (loaderText) loaderText.textContent = words[0];
  stopExplainLoader();
  _explainLoaderTimer = setInterval(function() {
    idx = (idx + 1) % words.length;
    if (loaderText) loaderText.textContent = words[idx];
  }, 1600);
}

function stopExplainLoader() {
  if (_explainLoaderTimer) {
    clearInterval(_explainLoaderTimer);
    _explainLoaderTimer = null;
  }
}

function showGameContent(roleId, data) {
  var lr = document.getElementById('explain-loading');
  var rr = document.getElementById('explain-result');
  if (lr) lr.classList.add('hidden');
  if (rr) rr.classList.remove('hidden');

  var gameCard = document.getElementById('explain-game-card');
  var gameEl = document.getElementById('explain-game-content');
  var explainCard = document.getElementById('explain-explain-card');
  var explainEl = document.getElementById('explain-explain-content');
  var metaEl = document.getElementById('explain-meta');

  var cardLabel = data.card_label || '📖 知识点讲解';
  var gameLabel = '🎮 闯关游戏';
  var explainLabel = cardLabel;

  if (gameCard) {
    var labelEl = gameCard.querySelector('.explain-card-label');
    if (labelEl) labelEl.textContent = gameLabel;
  }
  if (explainCard) {
    var labelEl2 = explainCard.querySelector('.explain-card-label');
    if (labelEl2) labelEl2.textContent = explainLabel;
  }

  if (gameEl) {
    gameEl.innerHTML = (data.game && data.game.trim())
      ? formatExplainText(data.game)
      : '<div class="explain-empty">这一关搭子没生成游戏剧情，内容在下方啦 ✨</div>';
  }
  if (explainEl) {
    explainEl.innerHTML = formatExplainText(data.explain || '搭子这一轮没有生成内容，请换个试试~');
  }
  if (metaEl) {
    var usedModel = data.used_model || '默认模型';
    var topic = data.topic || '';
    var name = data.buddy_name || '搭子';
    var emoji = data.buddy_emoji || '🌸';
    metaEl.innerHTML = '<span class="explain-badge">' + emoji + ' ' + escapeHtml(name) + '</span>' +
                       '<span class="explain-badge">📚 ' + escapeHtml(topic) + '</span>' +
                       '<span class="explain-badge">🤖 ' + escapeHtml(usedModel) + '</span>';
  }
}

function formatExplainText(text) {
  // 简单的 markdown 兼容：保留段落、空行、保留 emoji 不过滤
  if (!text) return '';
  var safe = escapeHtml(text);
  // 双换行分段
  return safe.split(/\n{2,}/).map(function(p){
    // 单换行用 <br>
    return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
  }).join('');
}

var _pendingRequestType = 'topic';

async function startExplain(requestType) {
  var topicInput = document.getElementById('explain-topic-input');
  var startBtn = document.getElementById('btn-start-explain');
  if (!topicInput) return;

  var topic = (topicInput.value || '').trim();
  if (!topic) {
    showToast('请先输入内容');
    topicInput.focus();
    return;
  }

  var roleId = (typeof currentBuddy !== 'undefined' && currentBuddy) ? currentBuddy : 'xiaodou';
  var reqType = requestType || _pendingRequestType || 'topic';

  if (startBtn) startBtn.disabled = true;
  showExplainLoading(roleId);

  try {
    var res = await fetch('/api/buddy/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ buddy_id: roleId, topic: topic, request_type: reqType })
    });
    var respData = await res.json();
    if (respData && respData.success) {
      showGameContent(roleId, respData);
    } else {
      var err = (respData && (respData.error || respData.tip)) || '讲解失败，请稍后重试';
      showToast(err);
      var lr = document.getElementById('explain-loading');
      if (lr) lr.classList.add('hidden');
    }
  } catch (e) {
    showToast('网络异常：' + e.message);
    var lr2 = document.getElementById('explain-loading');
    if (lr2) lr2.classList.add('hidden');
  } finally {
    if (startBtn) startBtn.disabled = false;
    stopExplainLoader();
  }
}

// ============================================================
// 账户状态卡（设置页面）
// ============================================================
function initAccountStatus() {
  var token = getToken();
  var username = getUsername();
  var usernameDiv = document.getElementById('account-username');
  var statusText = document.getElementById('account-status-text');
  var reloginBtn = document.getElementById('relogin-btn');
  var logoutBtn = document.getElementById('logout-btn');
  if (!usernameDiv) return;

  if (!token) {
    usernameDiv.textContent = '未登录';
    statusText.textContent = '当前为游客模式，AI 配置仅保存在本浏览器';
    if (reloginBtn) reloginBtn.style.display = 'inline-block';
    if (logoutBtn) logoutBtn.style.display = 'none';
  } else {
    usernameDiv.textContent = username || '已登录用户';
    statusText.textContent = 'Token 有效，可以使用 AI 配置持久化功能';
    if (reloginBtn) reloginBtn.style.display = 'none';
    if (logoutBtn) logoutBtn.style.display = 'inline-block';
  }

  // 改密码区域仅在登录后显示
  var pwdSection = document.getElementById('password-section');
  if (pwdSection) pwdSection.style.display = token ? 'block' : 'none';

  if (reloginBtn) {
    reloginBtn.onclick = function() {
      window.location.href = '/login';
    };
  }
  if (logoutBtn) {
    logoutBtn.onclick = function() {
      clearAuth();
      showToast('已退出登录');
      setTimeout(function() {
        if (typeof initAccountStatus === 'function') initAccountStatus();
      }, 600);
    };
  }
}

// ============================================================
// 修改密码
// ============================================================
function initChangePassword() {
  var btn = document.getElementById('btn-change-password');
  if (!btn) return;
  btn.addEventListener('click', function() {
    var oldPw = (document.getElementById('old-password') || {}).value || '';
    var newPw = (document.getElementById('new-password') || {}).value || '';
    var newPw2 = (document.getElementById('new-password2') || {}).value || '';

    if (!oldPw || !newPw) {
      showToast('请填写原密码和新密码');
      return;
    }
    if (newPw.length < 6) {
      showToast('新密码至少 6 位');
      return;
    }
    if (newPw !== newPw2) {
      showToast('两次输入的新密码不一致');
      return;
    }
    if (newPw === oldPw) {
      showToast('新密码不能和原密码相同');
      return;
    }

    btn.disabled = true;
    rawFetch('/api/auth/password', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + getToken()
      },
      body: JSON.stringify({ old_password: oldPw, new_password: newPw })
    })
      .then(function(res) {
        return res.json().then(function(data) { return { ok: res.ok, data: data }; });
      })
      .then(function(result) {
        if (result.ok && result.data.success) {
          showToast('密码已修改，下次请用新密码登录');
          ['old-password', 'new-password', 'new-password2'].forEach(function(id) {
            var el = document.getElementById(id);
            if (el) el.value = '';
          });
        } else {
          showToast((result.data && result.data.error) || '修改失败');
        }
      })
      .catch(function() {
        showToast('网络异常，请稍后再试');
      })
      .then(function() {
        btn.disabled = false;
      });
  });
}

// ============================================================
// 搭子对话（真实 AI + 内存保留）
// ============================================================

// 每个搭子的内存对话缓存 { buddy_id: [{sender,text,time}] }
var BUDDY_CONVERSATIONS = {
  xiaodou: [],
  aran: [],
  xuejie: [],
  senior: [],
  xiaoye: [],
  xj: [],
  azheng: []
};

// 搭子专属错误提示 / 思考语
// xuejie 是 senior 的前端别名，两个键都保留以避免任一侧取不到数据
var BUDDY_THINKING = {
  xiaodou: '小豆正在思考…',
  aran:    '阿燃正在燃烧斗志…',
  xuejie:  '小老师正在一步步推导…',
  senior:  '小老师正在一步步推导…',
  xiaoye:  '小夜正在静静思考…',
  xj:      '戏精正在编段子…',
  azheng:  '阿正正在理清逻辑…'
};

function _nowTimeStr() {
  var d = new Date();
  var h = d.getHours().toString().padStart(2,'0');
  var m = d.getMinutes().toString().padStart(2,'0');
  return h + ':' + m;
}

function chatContainer() {
  return document.getElementById('buddy-messages');
}

function renderChatMessage(sender, text, time, animate) {
  var container = chatContainer();
  if (!container) return;
  var meta = (typeof BUDDY_DATA !== 'undefined' && BUDDY_DATA[currentBuddy]) || {};
  var div = document.createElement('div');
  div.className = 'chat-message ' + sender + (animate ? ' message-new' : '');
  var avatar = sender === 'buddy' ? (meta.avatar || '🌸') : '👤';
  div.innerHTML =
    '<div class="message-avatar">' + avatar + '</div>' +
    '<div>' +
      '<div class="message-bubble">' + simpleMarkdownToHtml(text) + '</div>' +
      '<div class="message-time">' + (time || _nowTimeStr()) + '</div>' +
    '</div>';
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function simpleMarkdownToHtml(text) {
  if (!text) return '';
  var safe = escapeHtml(text);
  // 加粗、换行
  safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  safe = safe.replace(/\n/g, '<br>');
  return safe;
}

function saveMessageToMemory(sender, text) {
  if (!BUDDY_CONVERSATIONS[currentBuddy]) BUDDY_CONVERSATIONS[currentBuddy] = [];
  BUDDY_CONVERSATIONS[currentBuddy].push({
    sender: sender,
    text: text,
    time: _nowTimeStr()
  });
}

function addChatMessage(sender, text) {
  var time = _nowTimeStr();
  renderChatMessage(sender, text, time, true);
  saveMessageToMemory(sender, text);
}

function loadCurrentBuddyMessages() {
  var container = chatContainer();
  if (!container) return;
  container.innerHTML = '';
  var msgs = BUDDY_CONVERSATIONS[currentBuddy] || [];
  if (msgs.length === 0) {
    renderWelcomeToChat(currentBuddy);
    return;
  }
  msgs.forEach(function(m) {
    renderChatMessage(m.sender, m.text, m.time, false);
  });
}

function renderWelcomeToChat(buddyId) {
  var welcomes = {
    xiaodou: '嗨！我是小豆，你的学习搭子~ 🌟 有什么想聊的吗？',
    aran:    '哟！我是阿燃！🔥 准备燃烧你的学习热情了吗！',
    xuejie:  '你好，我是小老师 📚 哪里没听懂尽管问我。',
    xiaoye:  '晚上好…我是小夜 🌙 慢慢说，我听着呢。'
  };
  addChatMessage('buddy', welcomes[buddyId] || '你好！');
}

function addLoadingBubbleToChat() {
  var container = chatContainer();
  if (!container) return null;
  var meta = (typeof BUDDY_DATA !== 'undefined' && BUDDY_DATA[currentBuddy]) || {};
  var text = BUDDY_THINKING[currentBuddy] || '搭子正在思考…';
  var id = 'loading-' + Date.now();
  var div = document.createElement('div');
  div.id = id;
  div.className = 'chat-message loading';
  div.innerHTML =
    '<div class="message-avatar">' + (meta.avatar || '🌸') + '</div>' +
    '<div>' +
      '<div class="message-bubble" style="display:flex;align-items:center;gap:8px;">' +
        '<span class="loading-dots" style="display:inline-flex;gap:4px;">' +
          '<span style="width:8px;height:8px;background:#ddd;border-radius:50%;"></span>' +
          '<span style="width:8px;height:8px;background:#ddd;border-radius:50%;"></span>' +
          '<span style="width:8px;height:8px;background:#ddd;border-radius:50%;"></span>' +
        '</span>' +
        '<span style="font-size:13px;color:#8C8C8C;">' + text + '</span>' +
      '</div>' +
    '</div>';
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeLoadingBubbleFromChat(id) {
  if (!id) return;
  var el = document.getElementById(id);
  if (el && el.parentNode) el.parentNode.removeChild(el);
}

function getExplainMode() {
  var sel = document.querySelector('input[name="explain-mode"]:checked');
  return sel ? (sel.value || 'auto') : 'auto';
}

async function sendChatMessage() {
  var input = document.getElementById('buddy-input');
  var sendBtn = document.getElementById('btn-send-message');
  var text = (input ? input.value : '').trim();
  if (!text) return;
  if (sendBtn && sendBtn.disabled) return;
  if (input) input.value = '';
  if (sendBtn) sendBtn.disabled = true;

  addChatMessage('user', text);
  var loadingId = addLoadingBubbleToChat();

  try {
    var res = await fetch('/api/buddy/quick-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        buddy_id: currentBuddy,
        message: text,
        explain_mode: getExplainMode()
      })
    });
    var data = await res.json();
    removeLoadingBubbleFromChat(loadingId);
    if (data && data.success) {
      addChatMessage('buddy', data.reply || '…');
      bumpChatStat();
    } else {
      var err = (data && data.error) || 'AI 回复失败';
      var showCfg = /AI_AUTH|API_KEY|未配置|权限|密钥/.test(err);
      var html = escapeHtml(err);
      if (showCfg) {
        html += '<div class="chat-config-wrap"><button class="chat-config-btn" onclick="goToSettings()">⚙️ 前往设置配置 AI</button></div>';
      }
      addChatMessageHtml('buddy', html);
      showToast(err);
    }
  } catch (e) {
    removeLoadingBubbleFromChat(loadingId);
    var raw = (e && e.message) || '网络异常';
    var msg = raw;
    var showConfigBtn = false;
    // 403 细化提示
    if (raw.indexOf('AI_AUTH_403') >= 0) {
      msg = 'AI 权限验证失败，可能原因：1) API 密钥错误 2) 模型未开通权限 3) 账户额度已用完。\n详情：' + raw.replace(/^AI_AUTH_403:\s*/, '');
      showConfigBtn = true;
    } else if (raw.indexOf('API_KEY_INVALID') >= 0 || /403|Forbidden|401/.test(raw)) {
      msg = 'AI 密钥无效或权限不足：请检查设置中的 API 密钥是否正确。\n详情：' + raw.replace(/^API_KEY_INVALID:\s*/, '');
      showConfigBtn = true;
    } else if (raw.indexOf('AI_RATE_LIMIT') >= 0) {
      msg = 'AI 调用过于频繁，请稍后再试。';
    } else if (raw.indexOf('AI_NOT_FOUND') >= 0) {
      msg = 'API 地址或模型不存在，请检查设置。\n详情：' + raw;
      showConfigBtn = true;
    } else if (raw.indexOf('AI_SERVER_ERROR') >= 0) {
      msg = 'AI 服务器异常，请稍后重试。\n详情：' + raw;
    } else if (raw.indexOf('API_KEY_MISSING') >= 0 || /未配置|not configured|api_key/i.test(raw)) {
      msg = 'AI 模型未配置，请先前往设置页面配置。';
      showConfigBtn = true;
    } else {
      msg = '网络异常：' + raw;
    }

    // 构建错误消息 HTML（带前往设置按钮）
    var html = escapeHtml(msg).replace(/\n/g, '<br>');
    if (showConfigBtn) {
      html += '<div class="chat-config-wrap"><button class="chat-config-btn" onclick="goToSettings()">⚙️ 前往设置配置 AI</button></div>';
    }
    addChatMessageHtml('buddy', html);
    showToast('发送失败：' + msg.split('\n')[0]);
  } finally {
    if (sendBtn) sendBtn.disabled = false;
  }
}

// 跳到设置页
function goToSettings() {
  if (typeof window.__switchSection === 'function') {
    window.__switchSection('settings');
    showToast('请在「AI 配置」区域填写 API 密钥', 'info');
  } else {
    var nav = document.querySelector('[data-section="settings"]');
    if (nav) nav.click();
  }
}

// 渲染带 HTML 的消息气泡
function addChatMessageHtml(sender, html) {
  var container = document.getElementById('buddy-messages');
  if (!container) return;
  var meta = (typeof BUDDY_DATA !== 'undefined' && BUDDY_DATA[currentBuddy]) || {};
  var div = document.createElement('div');
  div.className = 'chat-message ' + sender + ' message-new';
  var avatar = sender === 'buddy' ? (meta.avatar || '🌸') : '👤';
  div.innerHTML =
    '<div class="message-avatar">' + avatar + '</div>' +
    '<div>' +
      '<div class="message-bubble">' + html + '</div>' +
      '<div class="message-time">' + _nowTimeStr() + '</div>' +
    '</div>';
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  // 不写入内存（避免保存带 HTML 标签的脏数据到历史）
}

function bumpChatStat() {
  var el = document.getElementById('stat-chats');
  if (!el) return;
  var n = parseInt(el.textContent || '0', 10) || 0;
  el.textContent = n + 1;
}

// ============================================================
// 历史记录
// ============================================================
function formatTimeAgo(isoString) {
  if (!isoString) return '';
  var d = new Date(isoString);
  if (isNaN(d.getTime())) return '';
  var diff = Date.now() - d.getTime();
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
  return (d.getMonth() + 1) + '月' + d.getDate() + '日';
}

async function loadConversationHistory() {
  var listEl = document.getElementById('buddy-history-list');
  if (!listEl) return;
  if (!getToken()) {
    listEl.innerHTML = '<div class="history-empty">登录后可查看历史对话</div>';
    return;
  }
  try {
    var res = await fetch('/api/buddy/conversations', {
      headers: { 'Authorization': 'Bearer ' + getToken() }
    });
    var data = await res.json();
    if (!data.success || !data.conversations || data.conversations.length === 0) {
      listEl.innerHTML = '<div class="history-empty">暂无历史对话</div>';
      return;
    }
    listEl.innerHTML = '';
    data.conversations.forEach(function(conv) {
      var item = document.createElement('div');
      item.className = 'history-item';
      item.dataset.convId = conv.id;
      item.innerHTML =
        '<div class="history-avatar">' + (conv.buddy_avatar || '🤖') + '</div>' +
        '<div class="history-info">' +
          '<div class="history-name">' + escapeHtml(conv.buddy_name || '对话') + '</div>' +
          '<div class="history-preview">' + escapeHtml(conv.preview || '新对话') + '</div>' +
          '<div class="history-meta">' + (conv.message_count || 0) + '条 · ' + formatTimeAgo(conv.updated_at) + '</div>' +
        '</div>' +
        '<button class="history-delete" data-conv-id="' + conv.id + '" title="删除">×</button>';

      item.addEventListener('click', function(e) {
        if (e.target.classList.contains('history-delete')) return;
        loadConversationDetail(conv.id);
      });

      var delBtn = item.querySelector('.history-delete');
      if (delBtn) {
        delBtn.addEventListener('click', function(e) {
          e.stopPropagation();
          if (confirm('确定删除这条历史对话吗？')) {
            deleteConversation(conv.id);
          }
        });
      }
      listEl.appendChild(item);
    });
  } catch (e) {
    listEl.innerHTML = '<div class="history-empty">加载失败</div>';
  }
}

async function loadConversationDetail(convId) {
  try {
    var res = await fetch('/api/buddy/conversation/' + convId, {
      headers: { 'Authorization': 'Bearer ' + getToken() }
    });
    var data = await res.json();
    if (!data.success) { showToast('加载失败'); return; }
    var conv = data.conversation;
    // 切换搭子
    if (typeof switchBuddy === 'function' && conv.buddy_id) {
      switchBuddy(conv.buddy_id);
    }
    // 恢复消息到内存（这里 messages 是 [{role,content,time?}] 格式）
    BUDDY_CONVERSATIONS[currentBuddy] = (conv.messages || []).map(function(m) {
      return {
        sender: m.role === 'user' ? 'user' : 'buddy',
        text: m.content || '',
        time: m.time || ''
      };
    });
    loadCurrentBuddyMessages();
    showToast('已加载历史对话');
  } catch (e) {
    showToast('加载失败：' + e.message);
  }
}

async function saveConversationToServer() {
  if (!getToken()) return;
  var messages = BUDDY_CONVERSATIONS[currentBuddy] || [];
  if (messages.length < 2) return; // 太少不保存
  try {
    await fetch('/api/buddy/conversation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + getToken()
      },
      body: JSON.stringify({
        buddy_id: currentBuddy,
        messages: messages
      })
    });
  } catch (e) {
    // 静默失败，不打断用户
  }
}

async function deleteConversation(convId) {
  try {
    var res = await fetch('/api/buddy/conversation/' + convId, {
      method: 'DELETE',
      headers: { 'Authorization': 'Bearer ' + getToken() }
    });
    var data = await res.json();
    if (data.success) {
      showToast('已删除');
      loadConversationHistory();
    } else {
      showToast('删除失败');
    }
  } catch (e) {
    showToast('删除失败：' + e.message);
  }
}

function startNewConversation() {
  // 先保存当前对话
  saveConversationToServer();
  // 清空当前内存
  BUDDY_CONVERSATIONS[currentBuddy] = [];
  // 重新渲染欢迎语
  var container = chatContainer();
  if (container) container.innerHTML = '';
  renderWelcomeToChat(currentBuddy);
  showToast('已开启新对话');
}
