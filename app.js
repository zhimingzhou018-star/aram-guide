const app = document.querySelector("#app");

const state = {
  payload: null,
  query: sessionStorage.getItem("hero-guide-query") || "",
};

function normalize(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]/g, "");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function route() {
  const match = location.hash.match(/^#\/champion\/([a-z0-9-]+)$/i);
  return match ? { name: "detail", slug: match[1] } : { name: "home" };
}

function matchesGuide(guide, query) {
  const needle = normalize(query);
  if (!needle) return true;
  const haystack = [guide.name, guide.title, guide.riotId, guide.buildName, ...(guide.aliases || [])]
    .map(normalize)
    .join("|");
  return haystack.includes(needle);
}

function cardTemplate(guide) {
  const published = guide.status === "published";
  const score = guide.winRate == null ? "—" : `${guide.winRate.toFixed(1)}%`;
  return `
    <button class="hero-card ${published ? "" : "is-building"}" type="button"
      data-slug="${escapeHtml(guide.slug)}" ${published ? "" : "aria-disabled=\"true\""}>
      <span class="portrait-wrap">
        ${guide.icon ? `<img src="${escapeHtml(guide.icon)}" alt="" width="96" height="96" loading="lazy" decoding="async" />` : ""}
        <span class="rank-mark">#${escapeHtml(guide.rank ?? "—")}</span>
      </span>
      <span class="hero-copy">
        <h2 class="hero-title">${escapeHtml(guide.name)}</h2>
        <p class="hero-epithet">${escapeHtml(guide.title)}</p>
      </span>
      <span class="card-foot">
        <span class="build-label">${escapeHtml(guide.buildName)}</span>
        <span class="score-block">
          <strong>${score}</strong>
          <span>胜率</span>
          ${published ? "" : '<em class="building-tag">制作中</em>'}
        </span>
      </span>
    </button>`;
}

function renderHome() {
  const { site, guides } = state.payload;
  const visible = guides.filter((guide) => matchesGuide(guide, state.query));
  document.title = site.title;
  app.innerHTML = `
    <section class="home-shell">
      <header class="site-header">
        <div class="brand-row">
          <div>
            <p class="brand-kicker">HEXTECH ARAM</p>
            <h1>海斗一图流</h1>
            <p class="brand-subtitle">抖音搜「芝士不是知识」</p>
          </div>
          <div class="version-chip">
            <strong>v${escapeHtml(site.version)}</strong>
            <span>${escapeHtml(site.dataDate)}</span>
          </div>
        </div>
      </header>
      <div class="search-wrap">
        <div class="search-field">
          <input id="heroSearch" type="search" autocomplete="off" placeholder="搜索英雄 / 外号 / 称号"
            aria-label="搜索英雄、外号或称号" value="${escapeHtml(state.query)}" />
          <button class="search-clear" type="button" aria-label="清空搜索">×</button>
        </div>
      </div>
      <div class="list-meta">
        <span>${visible.length} 位英雄</span>
        <span>按当前胜率排序</span>
      </div>
      <section class="guide-list" aria-label="英雄攻略列表">
        ${visible.length ? visible.map(cardTemplate).join("") : '<div class="empty-state"><p>没有找到这个英雄</p></div>'}
      </section>
    </section>`;

  const input = document.querySelector("#heroSearch");
  input.addEventListener("input", (event) => {
    state.query = event.target.value;
    sessionStorage.setItem("hero-guide-query", state.query);
    const filtered = guides.filter((guide) => matchesGuide(guide, state.query));
    document.querySelector(".list-meta span").textContent = `${filtered.length} 位英雄`;
    document.querySelector(".guide-list").innerHTML = filtered.length
      ? filtered.map(cardTemplate).join("")
      : '<div class="empty-state"><p>没有找到这个英雄</p></div>';
    bindCards();
  });
  document.querySelector(".search-clear").addEventListener("click", () => {
    state.query = "";
    sessionStorage.removeItem("hero-guide-query");
    renderHome();
    document.querySelector("#heroSearch").focus();
  });
  bindCards();
  requestAnimationFrame(() => window.scrollTo(0, Number(sessionStorage.getItem("hero-guide-scroll") || 0)));
}

function bindCards() {
  document.querySelectorAll(".hero-card:not(.is-building)").forEach((card) => {
    card.addEventListener("click", () => {
      sessionStorage.setItem("hero-guide-scroll", String(window.scrollY));
      location.hash = `#/champion/${card.dataset.slug}`;
    });
  });
}

function renderDetail(slug) {
  const { site, guides } = state.payload;
  const guide = guides.find((row) => row.slug === slug && row.status === "published");
  if (!guide) {
    location.hash = "#/";
    return;
  }
  document.title = `${guide.name}｜${guide.buildName}`;
  app.innerHTML = `
    <section class="detail-shell">
      <header class="detail-topbar">
        <button class="back-button" type="button" aria-label="返回首页">←</button>
        <div class="detail-heading">
          <strong>${escapeHtml(guide.name)}</strong>
          <span>${escapeHtml(guide.buildName)} · v${escapeHtml(site.version)}</span>
        </div>
        <span class="topbar-spacer" aria-hidden="true"></span>
      </header>
      <div class="guide-stage">
        <img class="guide-image" src="${escapeHtml(guide.images.preview)}" width="648" height="1152"
          loading="eager" decoding="async" fetchpriority="high"
          alt="${escapeHtml(guide.name)}${escapeHtml(guide.buildName)}海克斯大乱斗一图流" />
      </div>
    </section>`;
  document.querySelector(".back-button").addEventListener("click", () => {
    if (history.length > 1) history.back();
    else location.hash = "#/";
  });
  window.scrollTo(0, 0);
}

function render() {
  const current = route();
  if (current.name === "detail") renderDetail(current.slug);
  else renderHome();
}

async function start() {
  try {
    const response = await fetch("./data/guides.json?rev=3");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.payload = await response.json();
    render();
  } catch (error) {
    app.innerHTML = '<section class="error-state"><span class="loading-mark">!</span><p>攻略载入失败，请稍后刷新</p></section>';
  }
}

window.addEventListener("hashchange", render);
start();
