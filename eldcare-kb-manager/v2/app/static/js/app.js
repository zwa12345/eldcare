/* ELDCARE 前端应用入口 (原生 ES Module) */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const state = {
  view: "library",
  movies: [],
  categories: [],
  stats: null,
  currentMovie: null,
};

const api = {
  async health() {
    return (await fetch("/api/v2/health")).json();
  },
  async version() {
    return (await fetch("/api/v2/version")).json();
  },
  async listMovies({ page = 1, size = 30, q, category } = {}) {
    const p = new URLSearchParams({ page, size });
    if (q) p.set("q", q);
    if (category) p.set("category", category);
    return (await fetch("/api/v2/library/movies?" + p)).json();
  },
  async listCategories() {
    return (await fetch("/api/v2/library/categories")).json();
  },
  async stats() {
    return (await fetch("/api/v2/library/stats")).json();
  },
};

function fmtSize(b) {
  if (!b) return "";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return `${b.toFixed(i ? 1 : 0)} ${u[i]}`;
}

function escapeHtml(s) {
  if (!s) return "";
  return s.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderMovies(movies) {
  const grid = $("#movie-grid");
  if (!movies.length) {
    grid.innerHTML = '<div class="empty">没有影片。先到设置里扫描媒体目录，或添加片源。</div>';
    return;
  }
  grid.innerHTML = movies.map(m => {
    const resBadge = m.resolution ? `<span class="badge res">${m.resolution}</span>` : "";
    const year = m.year ?? "";
    const rating = m.rating ? `⭐ ${m.rating.toFixed(1)}` : "";
    return `
      <div class="card" data-id="${m.id}">
        <div class="poster">
          ${m.poster_url
            ? `<img src="${escapeHtml(m.poster_url)}" loading="lazy" alt="${escapeHtml(m.title)}" />`
            : `<span>${escapeHtml(m.title)}</span>`}
        </div>
        <div class="card-info">
          <div class="card-title" title="${escapeHtml(m.title)}">${escapeHtml(m.title)}</div>
          <div class="card-meta">
            ${resBadge}
            <span>${year}</span>
            <span>${rating}</span>
          </div>
        </div>
      </div>`;
  }).join("");

  grid.querySelectorAll(".card").forEach(card => {
    card.addEventListener("click", () => playMovie(parseInt(card.dataset.id, 10)));
  });
}

function renderCategories(cats) {
  const grid = $("#category-grid");
  if (!cats.length) {
    grid.innerHTML = '<div class="empty">暂无分类</div>';
    return;
  }
  const ICONS = {
    "动作": "💥", "喜剧": "😂", "爱情": "💕", "科幻": "🚀", "恐怖": "👻",
    "动画": "🎨", "悬疑": "🔍", "战争": "⚔️", "剧情": "🎭", "纪录": "📹",
  };
  grid.innerHTML = cats.map(c => `
    <div class="cat-card" data-slug="${escapeHtml(c.slug)}">
      <div class="cat-icon">${ICONS[c.name] || "🎬"}</div>
      <div class="cat-name">${escapeHtml(c.name)}</div>
    </div>`).join("");
  grid.querySelectorAll(".cat-card").forEach(el => {
    el.addEventListener("click", async () => {
      const slug = el.dataset.slug;
      switchTab("library");
      const r = await api.listMovies({ category: slug });
      state.movies = r.items || [];
      renderMovies(state.movies);
    });
  });
}

function renderStats(s) {
  $("#stats-pill").textContent = `${s.total_movies} 部 · ${s.total_categories} 分类`;
}

async function playMovie(id) {
  const m = state.movies.find(x => x.id === id);
  state.currentMovie = m;
  switchTab("player");
  const v = $("#player");
  v.src = `/api/v2/player/stream/${id}`;
  v.load();
  $("#player-info").innerHTML = `
    <h2>${escapeHtml(m?.title || "")}</h2>
    <p>${escapeHtml(m?.overview || "暂无简介")}</p>
    <div style="margin-top: 8px; color: var(--text-muted); font-size: 13px;">
      ${m?.year ?? ""} · ${m?.resolution ?? ""} · ${m?.video_codec ?? ""} · ${fmtSize(m?.file_size)}
    </div>`;
}

function switchTab(name) {
  state.view = name;
  $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  $$(".view").forEach(v => v.classList.toggle("active", v.id === `view-${name}`));
}

async function refresh() {
  try {
    const [mv, cs, st] = await Promise.all([
      api.listMovies({ size: 60 }),
      api.listCategories(),
      api.stats(),
    ]);
    state.movies = mv.items || [];
    state.categories = cs || [];
    state.stats = st;
    renderMovies(state.movies);
    renderCategories(state.categories);
    renderStats(st);
  } catch (e) {
    $("#movie-grid").innerHTML = `<div class="empty">数据加载失败：${e.message}<br/><small>请检查后端是否在 8090 端口运行</small></div>`;
  }
}

async function loadSettings() {
  try {
    const h = await api.health();
    $("#set-role").textContent = h.node_role;
    $("#set-instance").textContent = h.instance_id;
    $("#set-db").textContent = `${h.db}（${h.db_path}）`;
    $("#set-movies").textContent = h.movies_dir;
  } catch (e) {
    // 静默
  }
}

// ====== Wire up ======
$$(".tab").forEach(tab => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});

let searchTimer;
$("#search-input").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    const q = e.target.value.trim();
    const r = await api.listMovies({ q, size: 60 });
    state.movies = r.items || [];
    renderMovies(state.movies);
  }, 300);
});

refresh();
loadSettings();
