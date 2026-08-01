const app = document.querySelector("#app");

const state = {
  payload: null,
  query: sessionStorage.getItem("hero-guide-query") || "",
};
const MAX_AUTO_PREFETCHED_GUIDES = 6;
const SEARCH_CAPTURE_DELAY_MS = 450;
const SESSION_GUIDE_VIEWS_KEY = "hero-guide-session-views";
const prefetchedGuideImages = new Set();
const automaticallyPrefetchedGuideImages = new Set();
let cardPrefetchObserver = null;
let searchCaptureTimer = null;
let previousRoute = null;

function capture(eventName, properties = {}) {
  window.ARAM_ANALYTICS?.capture(eventName, properties);
}

function guideEventProperties(guide) {
  return {
    hero_slug: guide.slug,
    hero_name: guide.name,
    rank: guide.rank,
    build_key: guide.buildKey,
    build_name: guide.buildName,
  };
}

function recordGuideView(guide) {
  let viewedSlugs = [];
  try {
    viewedSlugs = JSON.parse(sessionStorage.getItem(SESSION_GUIDE_VIEWS_KEY) || "[]");
  } catch {
    viewedSlugs = [];
  }
  const uniqueViews = new Set(Array.isArray(viewedSlugs) ? viewedSlugs : []);
  uniqueViews.add(guide.slug);
  sessionStorage.setItem(SESSION_GUIDE_VIEWS_KEY, JSON.stringify([...uniqueViews]));
  capture("guide_view", {
    ...guideEventProperties(guide),
    session_unique_guides_viewed: uniqueViews.size,
  });
}

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
    clearTimeout(searchCaptureTimer);
    const query = state.query.trim();
    if (query) {
      searchCaptureTimer = setTimeout(() => {
        capture("hero_search", {
          query,
          query_length: query.length,
          result_count: filtered.length,
          has_results: filtered.length > 0,
        });
      }, SEARCH_CAPTURE_DELAY_MS);
    }
    bindCards();
  });
  document.querySelector(".search-clear").addEventListener("click", () => {
    clearTimeout(searchCaptureTimer);
    state.query = "";
    sessionStorage.removeItem("hero-guide-query");
    renderHome();
    document.querySelector("#heroSearch").focus();
  });
  bindCards();
  requestAnimationFrame(() => window.scrollTo(0, Number(sessionStorage.getItem("hero-guide-scroll") || 0)));
  capture("home_view", {
    query: state.query,
    result_count: visible.length,
    guide_count: guides.length,
  });
}

function bindCards() {
  const guideBySlug = new Map(state.payload.guides.map((guide) => [guide.slug, guide]));
  const prefetchGuide = (slug, { automatic = false } = {}) => {
    const preview = guideBySlug.get(slug)?.images?.preview;
    if (automatic && automaticallyPrefetchedGuideImages.size >= MAX_AUTO_PREFETCHED_GUIDES) return;
    if (!preview || prefetchedGuideImages.has(preview)) return;
    prefetchedGuideImages.add(preview);
    if (automatic) automaticallyPrefetchedGuideImages.add(preview);
    const link = document.createElement("link");
    link.rel = "prefetch";
    link.as = "image";
    link.href = preview;
    document.head.appendChild(link);
  };
  cardPrefetchObserver?.disconnect();
  cardPrefetchObserver = "IntersectionObserver" in window
    ? new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          prefetchGuide(entry.target.dataset.slug, { automatic: true });
          cardPrefetchObserver.unobserve(entry.target);
        });
      }, { rootMargin: "240px 0px" })
    : null;
  document.querySelectorAll(".hero-card:not(.is-building)").forEach((card) => {
    cardPrefetchObserver?.observe(card);
    card.addEventListener("pointerenter", () => prefetchGuide(card.dataset.slug), { once: true });
    card.addEventListener("focusin", () => prefetchGuide(card.dataset.slug), { once: true });
    card.addEventListener("touchstart", () => prefetchGuide(card.dataset.slug), {
      once: true,
      passive: true,
    });
    card.addEventListener("click", () => {
      const guide = guideBySlug.get(card.dataset.slug);
      capture("hero_card_click", {
        ...guideEventProperties(guide),
        query: state.query,
      });
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
    location.hash = "#/";
  });
  recordGuideView(guide);
  window.scrollTo(0, 0);
}

function render() {
  const current = route();
  if (previousRoute?.name === "detail" && current.name === "home") {
    const previousGuide = state.payload.guides.find((guide) => guide.slug === previousRoute.slug);
    capture("return_home", previousGuide ? guideEventProperties(previousGuide) : {
      hero_slug: previousRoute.slug,
    });
  }
  previousRoute = current;
  if (current.name === "detail") renderDetail(current.slug);
  else renderHome();
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js", { updateViaCache: "none" }).catch(() => {});
  });
}

async function start() {
  try {
    const response = await fetch("./data/guides.json?rev=6");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.payload = await response.json();
    render();
  } catch (error) {
    app.innerHTML = '<section class="error-state"><span class="loading-mark">!</span><p>攻略载入失败，请稍后刷新</p></section>';
  }
}

window.addEventListener("hashchange", render);
registerServiceWorker();
start();
