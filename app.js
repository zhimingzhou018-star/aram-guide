const app = document.querySelector("#app");

const memorySession = new Map();

function readSession(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return memorySession.get(key) ?? null;
  }
}

function writeSession(key, value) {
  memorySession.set(key, String(value));
  try {
    sessionStorage.setItem(key, String(value));
  } catch {
    // Some embedded mobile browsers expose storage but deny access to it.
  }
}

function removeSession(key) {
  memorySession.delete(key);
  try {
    sessionStorage.removeItem(key);
  } catch {
    // Keep the in-memory fallback usable when persistent storage is restricted.
  }
}

const state = {
  index: null,
  query: readSession("hero-guide-query") || "",
  guideCache: new Map(),
  selectedBuilds: new Map(),
};

const SEARCH_CAPTURE_DELAY_MS = 450;
const SESSION_GUIDE_VIEWS_KEY = "hero-guide-session-views";
const prefetchedSlugs = new Set();
let previousRoute = null;
let searchCaptureTimer = null;

function capture(eventName, properties = {}) {
  window.ARAM_ANALYTICS?.capture(eventName, properties);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalize(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]/g, "");
}

function matchesGuide(guide, query) {
  const needle = normalize(query);
  if (!needle) return true;
  return [guide.name, guide.title, guide.riotId, guide.buildName, ...(guide.aliases || [])]
    .map(normalize)
    .some((value) => value.includes(needle));
}

function currentRoute() {
  const match = location.hash.match(/^#\/champion\/([a-z0-9-]+)$/i);
  return match ? { name: "detail", slug: match[1] } : { name: "home" };
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function loadIndex() {
  return fetch("./data/index.json?rev=22").then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
}

async function loadGuide(slug) {
  if (state.guideCache.has(slug)) return state.guideCache.get(slug);
  const guide = await fetch(`./data/heroes/${encodeURIComponent(slug)}.json?rev=22`).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
  if (guide.schemaVersion !== 3 || guide.hero?.slug !== slug) {
    throw new Error("Invalid hero guide payload");
  }
  state.guideCache.set(slug, guide);
  return guide;
}

function guideEventProperties(guide) {
  const hero = guide.hero || guide;
  const ranking = guide.ranking || guide;
  const build = guide.build || guide;
  return {
    hero_slug: hero.slug,
    hero_name: hero.name,
    rank: ranking.rank,
    build_key: build.key || build.buildKey,
    build_name: build.name || build.buildName,
  };
}

function recordGuideView(guide) {
  let viewedSlugs = [];
  try {
    viewedSlugs = JSON.parse(readSession(SESSION_GUIDE_VIEWS_KEY) || "[]");
  } catch {
    viewedSlugs = [];
  }
  const uniqueViews = new Set(Array.isArray(viewedSlugs) ? viewedSlugs : []);
  uniqueViews.add(guide.hero.slug);
  writeSession(SESSION_GUIDE_VIEWS_KEY, JSON.stringify([...uniqueViews]));
  capture("guide_view", {
    ...guideEventProperties(guide),
    session_unique_guides_viewed: uniqueViews.size,
  });
}

function heroCard(guide) {
  const winRate = guide.winRate == null ? "—" : `${Number(guide.winRate).toFixed(1)}%`;
  return `
    <button class="hero-card" type="button" data-slug="${escapeHtml(guide.slug)}">
      <span class="portrait-wrap">
        <img src="${escapeHtml(guide.icon)}" alt="" width="96" height="96" loading="lazy" decoding="async" />
        <span class="rank-mark">#${escapeHtml(guide.rank ?? "—")}</span>
      </span>
      <span class="hero-copy">
        <strong class="hero-name">${escapeHtml(guide.name)}</strong>
        <span class="hero-title">${escapeHtml(guide.title)}</span>
        <span class="build-label">${escapeHtml(guide.buildName)}</span>
      </span>
      <span class="win-rate"><strong>${winRate}</strong><small>胜率</small></span>
    </button>`;
}

function renderHeroGrid(guides) {
  const grid = document.querySelector(".guide-list");
  const count = document.querySelector("[data-result-count]");
  if (count) count.textContent = `${guides.length} 位英雄`;
  if (grid) {
    grid.innerHTML = guides.length
      ? guides.map(heroCard).join("")
      : '<div class="empty-state"><span>未命中</span><p>换个英雄名、外号或称号试试</p></div>';
  }
  bindHeroCards();
}

function renderHome() {
  const { site, guides } = state.index;
  const visible = guides.filter((guide) => matchesGuide(guide, state.query));
  document.title = site.title;
  app.innerHTML = `
    <section class="home-shell">
      <header class="site-header">
        <div class="brand-lockup">
          <span class="brand-index">H / ARAM</span>
          <div>
            <h1>海斗一图流</h1>
            <p>抖音搜「芝士不是知识」</p>
          </div>
        </div>
        <div class="version-chip"><strong>V${escapeHtml(site.version)}</strong><span>${escapeHtml(site.dataDate)}</span></div>
      </header>
      <div class="search-dock">
        <label class="search-field">
          <span aria-hidden="true">⌕</span>
          <input id="heroSearch" type="search" autocomplete="off" placeholder="搜索英雄 / 外号 / 称号"
            aria-label="搜索英雄、外号或称号" value="${escapeHtml(state.query)}" />
          <button class="search-clear" type="button" aria-label="清空搜索">×</button>
        </label>
      </div>
      <div class="list-meta"><span data-result-count>${visible.length} 位英雄</span><span>按胜率排序</span></div>
      <section class="guide-list" aria-label="英雄攻略列表"></section>
    </section>`;

  renderHeroGrid(visible);
  const input = document.querySelector("#heroSearch");
  input.addEventListener("input", (event) => {
    state.query = event.target.value;
    writeSession("hero-guide-query", state.query);
    const filtered = guides.filter((guide) => matchesGuide(guide, state.query));
    renderHeroGrid(filtered);
    clearTimeout(searchCaptureTimer);
    if (state.query.trim()) {
      searchCaptureTimer = setTimeout(() => capture("hero_search", {
        query: state.query.trim(),
        query_length: state.query.trim().length,
        result_count: filtered.length,
        has_results: filtered.length > 0,
      }), SEARCH_CAPTURE_DELAY_MS);
    }
  });
  document.querySelector(".search-clear").addEventListener("click", () => {
    state.query = "";
    removeSession("hero-guide-query");
    input.value = "";
    renderHeroGrid(guides);
    input.focus();
  });
  requestAnimationFrame(() => window.scrollTo(0, Number(readSession("hero-guide-scroll") || 0)));
  capture("home_view", { query: state.query, result_count: visible.length, guide_count: guides.length });
}

function prefetchGuide(slug) {
  if (prefetchedSlugs.has(slug) || state.guideCache.has(slug)) return;
  prefetchedSlugs.add(slug);
  const link = document.createElement("link");
  link.rel = "prefetch";
  link.as = "fetch";
  link.crossOrigin = "anonymous";
  link.href = `./data/heroes/${encodeURIComponent(slug)}.json?rev=22`;
  document.head.appendChild(link);
}

function bindHeroCards() {
  const bySlug = new Map(state.index.guides.map((guide) => [guide.slug, guide]));
  document.querySelectorAll(".hero-card").forEach((card) => {
    card.addEventListener("pointerenter", () => prefetchGuide(card.dataset.slug), { once: true });
    card.addEventListener("focusin", () => prefetchGuide(card.dataset.slug), { once: true });
    card.addEventListener("touchstart", () => prefetchGuide(card.dataset.slug), { once: true, passive: true });
    card.addEventListener("click", () => {
      const guide = bySlug.get(card.dataset.slug);
      capture("hero_card_click", { ...guideEventProperties(guide), query: state.query });
      writeSession("hero-guide-scroll", String(window.scrollY));
      location.hash = `#/champion/${card.dataset.slug}`;
    });
  });
}

function ModuleShell(title, eyebrow, content, className = "") {
  return `
    <section class="guide-module ${className}">
      <header class="module-heading"><span>${escapeHtml(eyebrow)}</span><h2>${escapeHtml(title)}</h2></header>
      ${content}
    </section>`;
}

function HeroHeader(guide) {
  const { hero, ranking, build } = guide;
  return `
    <section class="hero-overview">
      <img class="overview-portrait" src="${escapeHtml(hero.icon)}" alt="${escapeHtml(hero.name)}" width="128" height="128" decoding="async" />
      <div class="overview-copy">
        <span class="overview-kicker">#${escapeHtml(ranking.rank)} · ${escapeHtml(ranking.tier)}级</span>
        <h1>${escapeHtml(hero.name)}</h1>
        <p>${escapeHtml(hero.title)}</p>
        <strong>${escapeHtml(build.name)}</strong>
      </div>
      <div class="overview-score"><strong>${Number(ranking.winRatePercent).toFixed(1)}%</strong><span>当前胜率</span></div>
    </section>`;
}

function iconTile(entry, className = "") {
  return `
    <li class="icon-tile ${className}">
      <img src="${escapeHtml(entry.icon)}" alt="" width="64" height="64" loading="lazy" decoding="async" />
      <span>${escapeHtml(entry.name)}</span>
    </li>`;
}

function SpellAndSkillModule(guide) {
  const abilityByKey = new Map((guide.hero.abilities || []).map((ability) => [ability.key, ability]));
  const skillKeys = guide.skillOrder.split(">");
  const spells = guide.summonerSpells.map((spell) => iconTile(spell, "spell-tile")).join("");
  const skills = skillKeys.map((key, index) => {
    const ability = abilityByKey.get(key);
    return `
      <li class="skill-step">
        <span>${index + 1}</span>
        ${ability ? `<img src="${escapeHtml(ability.icon)}" alt="" width="56" height="56" loading="lazy" decoding="async" />` : ""}
        <strong>${escapeHtml(key)}</strong>
      </li>`;
  }).join("");
  return ModuleShell("召唤师技能与加点", "LOADOUT 01", `
    <div class="spell-skill-layout">
      <div><p class="micro-label">召唤师技能</p><ul class="spell-list">${spells}</ul></div>
      <div><p class="micro-label">技能优先级</p><ol class="skill-order">${skills}</ol></div>
    </div>`);
}

function ItemModule(guide) {
  const starters = guide.items.starter.map((item) => iconTile(item)).join("");
  const recommended = guide.items.recommended.map((item, index) => `
    <li class="item-tile ${index < 3 ? "is-core" : ""}">
      <span class="item-index">${String(index + 1).padStart(2, "0")}</span>
      <img src="${escapeHtml(item.icon)}" alt="" width="72" height="72" loading="lazy" decoding="async" />
      <strong>${escapeHtml(item.name)}</strong>
    </li>`).join("");
  return ModuleShell("推荐出装", "LOADOUT 02", `
    <div class="item-section"><p class="micro-label">出门装</p><ul class="starter-list">${starters}</ul></div>
    <div class="item-section"><p class="micro-label">六件成装 <span>前三件为核心顺序</span></p><ol class="item-grid">${recommended}</ol></div>`);
}

function AugmentTierModule(title, rarity, entries) {
  return `
    <section class="augment-tier augment-${escapeHtml(rarity)}">
      <header><span>${escapeHtml(title)}</span><small>${entries.length} 个推荐</small></header>
      <ul>${entries.map((entry) => iconTile(entry)).join("")}</ul>
    </section>`;
}

function AugmentCombinationModule(guide) {
  const augmentMap = new Map();
  for (const rarity of ["prismatic", "gold", "silver"]) {
    for (const augment of guide.augments[rarity]) augmentMap.set(Number(augment.id), augment);
  }
  const rows = guide.augments.combinations.map((combination) => {
    const augments = combination.ids.map((id, index) => augmentMap.get(Number(id)) || {
      id,
      name: combination.names[index],
      icon: "",
    });
    return `
      <li class="combo-row">
        <span class="combo-rank">#${escapeHtml(combination.rank)}</span>
        <span class="combo-pair">${augments.map((augment) => augment.icon
          ? `<img src="${escapeHtml(augment.icon)}" alt="${escapeHtml(augment.name)}" width="48" height="48" loading="lazy" decoding="async" />`
          : "").join("")}</span>
        <span class="combo-names">${augments.map((augment) => escapeHtml(augment.name)).join(" + ")}</span>
        <strong>${(Number(combination.winRate) * 100).toFixed(1)}%</strong>
      </li>`;
  }).join("");
  return rows ? `<div class="combo-block"><p class="micro-label">高胜率组合</p><ol>${rows}</ol></div>` : "";
}

function GameplayModule(guide) {
  const points = guide.gameplay.summary.map((point, index) => `
    <li><span>${String(index + 1).padStart(2, "0")}</span><p>${escapeHtml(point)}</p></li>`).join("");
  return ModuleShell("玩法摘要", "PLAYBOOK", `<ol class="gameplay-list">${points}</ol>`, "gameplay-module");
}

function FigmaLoadoutIcon(entry, className = "") {
  return `
    <li class="figma-loadout-icon ${className}">
      <img src="${escapeHtml(entry.icon)}" alt="" width="64" height="64" loading="lazy" decoding="async" />
      <span>${escapeHtml(entry.name)}</span>
    </li>`;
}

function FigmaHeroHeader(guide) {
  const abilityByKey = new Map((guide.hero.abilities || []).map((ability) => [ability.key, ability]));
  const skillKeys = guide.skillOrder.split(">");
  return `
    <section class="figma-hero-header">
      <a class="figma-home-hotspot" href="#/" aria-label="返回首页"></a>
      <img class="figma-hero-portrait" src="${escapeHtml(guide.hero.icon)}" alt="${escapeHtml(guide.hero.name)}" width="128" height="128" decoding="async" />
      <div class="figma-hero-copy">
        <p>${escapeHtml(guide.hero.name)}</p>
        <h1>${escapeHtml(guide.hero.title)}</h1>
      </div>
      <div class="figma-header-loadout">
        <div class="figma-header-group">
          <strong>召唤师技能</strong>
          <ul>${guide.summonerSpells.map((spell) => FigmaLoadoutIcon(spell, "figma-spell-icon")).join("")}</ul>
        </div>
        <div class="figma-header-group figma-skill-group">
          <strong>技能加点</strong>
          <ol>${skillKeys.map((key) => {
            const ability = abilityByKey.get(key);
            return ability ? `
              <li>
                <img src="${escapeHtml(ability.icon)}" alt="" width="56" height="56" loading="lazy" decoding="async" />
                <span>${escapeHtml(key)}</span>
              </li>` : "";
          }).join("")}</ol>
        </div>
      </div>
    </section>`;
}

function FigmaItemTile(item) {
  return `
    <li>
      <img src="${escapeHtml(item.icon)}" alt="" width="72" height="72" loading="lazy" decoding="async" />
      <span>${escapeHtml(item.name)}</span>
    </li>`;
}

function FigmaAugmentTier(title, rarity, entries) {
  return `
    <section class="figma-augment-tier figma-augment-${escapeHtml(rarity)}">
      <header><strong>${escapeHtml(title)}</strong><span></span></header>
      <ul>${entries.slice(0, 6).map((entry) => FigmaLoadoutIcon(entry)).join("")}</ul>
    </section>`;
}

function FigmaCombinations(guide) {
  const augmentMap = new Map();
  for (const rarity of ["prismatic", "gold", "silver"]) {
    for (const augment of guide.augments[rarity]) augmentMap.set(Number(augment.id), augment);
  }
  const combinations = guide.augments.combinations.slice(0, 4).map((combination) => {
    const augments = combination.ids.map((id, index) => augmentMap.get(Number(id)) || {
      id,
      name: combination.names[index],
      icon: `assets/resources/augments/${id}.webp`,
    });
    return `
      <li>
        <span class="figma-combo-rank">#${escapeHtml(combination.rank)}</span>
        <span class="figma-combo-augment">
          <img src="${escapeHtml(augments[0].icon)}" alt="" width="48" height="48" loading="lazy" decoding="async" />
          <strong>${escapeHtml(augments[0].name)}</strong>
        </span>
        <span class="figma-combo-plus">+</span>
        <span class="figma-combo-augment">
          <img src="${escapeHtml(augments[1].icon)}" alt="" width="48" height="48" loading="lazy" decoding="async" />
          <strong>${escapeHtml(augments[1].name)}</strong>
        </span>
      </li>`;
  }).join("");
  return `
    <section class="figma-combinations">
      <header><h2>海克斯组合</h2><span></span></header>
      <ol>${combinations}</ol>
    </section>`;
}

function selectedBuildGuide(guide, buildKey) {
  const build = guide.builds.find((row) => row.key === buildKey) || guide.builds[0];
  return { ...guide, build, items: build.items };
}

function isLowSampleBuild(build) {
  const sampleCount = Number(build.sampleCount || 0);
  return Boolean(build.lowSampleWarning) || (sampleCount >= 100 && sampleCount < 200);
}

function FigmaBuildTabs(guide, activeBuild) {
  return `
    <nav class="figma-build-strip" aria-label="流派选择" data-build-count="${guide.builds.length}">
      ${guide.builds.map((build) => {
        const active = build.key === activeBuild.key;
        const winRate = Number(build.coreProfile?.winRate || 0) * 100;
        const lowSample = isLowSampleBuild(build);
        return `
          <button class="figma-build-tab${active ? " is-active" : ""}${lowSample ? " has-low-sample" : ""}" type="button"
            data-build-key="${escapeHtml(build.key)}" aria-pressed="${active}"
            aria-label="${escapeHtml(build.name)}，胜率 ${winRate.toFixed(1)}%${lowSample ? "，低样本警告" : ""}">
            ${lowSample ? '<span class="figma-build-warning-badge" aria-hidden="true">!</span>' : ""}
            <span class="figma-build-name">${escapeHtml(build.name)}</span>
            <span class="figma-build-stat"><span>胜率</span><strong class="figma-build-winrate">${winRate.toFixed(1)}%</strong></span>
          </button>`;
      }).join("")}
    </nav>`;
}

function FigmaGuidePage(guide, buildKey = guide.defaultBuildKey) {
  const selectedGuide = selectedBuildGuide(guide, buildKey);
  const gameplay = selectedGuide.gameplay.summary.join(" ");
  const lowSampleWarning = isLowSampleBuild(selectedGuide.build);
  return `
    <article class="figma-poster">
      <div class="figma-accent-line"></div>
      <div class="figma-poster-body">
        ${FigmaHeroHeader(selectedGuide)}
        ${FigmaBuildTabs(guide, selectedGuide.build)}
        ${lowSampleWarning ? '<p class="figma-low-sample-warning"><strong>!</strong> 低样本警告 · 不足200场，仅供参考</p>' : ""}
        <p class="figma-gameplay"><strong>玩法：</strong>${escapeHtml(gameplay)}</p>
        <section class="figma-items">
          <h2>推荐出装</h2>
          <p>出门装</p>
          <ul class="figma-starter-items">${selectedGuide.items.starter.map(FigmaItemTile).join("")}</ul>
          <p>推荐选择</p>
          <ol class="figma-recommended-items">${selectedGuide.items.recommended.slice(0, 6).map(FigmaItemTile).join("")}</ol>
        </section>
        <section class="figma-augments">
          <h2>海克斯推荐</h2>
          ${FigmaAugmentTier("棱彩", "prismatic", selectedGuide.augments.prismatic)}
          ${FigmaAugmentTier("金色", "gold", selectedGuide.augments.gold)}
          ${FigmaAugmentTier("银色", "silver", selectedGuide.augments.silver)}
        </section>
        ${FigmaCombinations(selectedGuide)}
      </div>
    </article>`;
}

function LegacyPosterFallback(indexGuide, message = "模块数据暂不可用") {
  if (!indexGuide?.legacyPoster) {
    return `<section class="error-state"><span>!</span><p>${escapeHtml(message)}</p><a href="#/">返回首页</a></section>`;
  }
  return `
    <section class="fallback-shell">
      <div class="fallback-notice"><strong>${escapeHtml(message)}</strong><span>暂时显示上一版攻略</span></div>
      <img src="${escapeHtml(indexGuide.legacyPoster)}" alt="${escapeHtml(indexGuide.name)}旧版攻略" width="648" height="1152" />
    </section>`;
}

function renderDetailTopbar(guide) {
  return `
    <header class="detail-topbar">
      <a class="back-button" href="#/" aria-label="返回首页"><span aria-hidden="true">←</span><em>返回首页</em></a>
      <div class="detail-heading"><strong>${escapeHtml(guide.hero.name)}</strong><span>${escapeHtml(guide.build.name)} · V${escapeHtml(state.index.site.version)}</span></div>
      <span class="topbar-spacer" aria-hidden="true"></span>
    </header>`;
}

async function renderDetail(slug) {
  const indexGuide = state.index.guides.find((guide) => guide.slug === slug);
  if (!indexGuide) {
    location.hash = "#/";
    return;
  }
  app.innerHTML = `<section class="detail-shell"><header class="detail-topbar detail-loading"><a class="back-button" href="#/">←</a><div class="detail-heading"><strong>${escapeHtml(indexGuide.name)}</strong><span>加载模块数据</span></div><span></span></header><div class="module-skeleton"></div></section>`;
  try {
    const guide = await loadGuide(slug);
    const renderSelectedBuild = (buildKey) => {
      const selectedGuide = selectedBuildGuide(guide, buildKey);
      state.selectedBuilds.set(slug, selectedGuide.build.key);
      document.title = `${guide.hero.name}｜${selectedGuide.build.name}`;
      app.innerHTML = `<section class="detail-shell figma-detail-shell">${FigmaGuidePage(guide, selectedGuide.build.key)}</section>`;
      document.querySelectorAll(".figma-build-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
          if (tab.dataset.buildKey === selectedGuide.build.key) return;
          capture("build_switch", {
            ...guideEventProperties(guide),
            from_build_key: selectedGuide.build.key,
            to_build_key: tab.dataset.buildKey,
          });
          renderSelectedBuild(tab.dataset.buildKey);
        });
      });
    };
    renderSelectedBuild(state.selectedBuilds.get(slug) || guide.defaultBuildKey);
    recordGuideView(guide);
  } catch (error) {
    app.innerHTML = `<section class="detail-shell"><header class="detail-topbar"><a class="back-button" href="#/">← <em>返回首页</em></a><div class="detail-heading"><strong>${escapeHtml(indexGuide.name)}</strong><span>旧版兜底</span></div><span></span></header>${LegacyPosterFallback(indexGuide)}</section>`;
  }
  window.scrollTo(0, 0);
}

async function renderRoute() {
  const route = currentRoute();
  if (previousRoute?.name === "detail" && route.name === "home") {
    const guide = state.index.guides.find((entry) => entry.slug === previousRoute.slug);
    capture("return_home", guide ? guideEventProperties(guide) : { hero_slug: previousRoute.slug });
  }
  previousRoute = route;
  if (route.name === "detail") await renderDetail(route.slug);
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
    state.index = await loadIndex();
    await renderRoute();
  } catch (error) {
    app.innerHTML = '<section class="error-state"><span>!</span><p>攻略加载失败，请稍后刷新</p></section>';
  }
}

window.addEventListener("hashchange", renderRoute);
registerServiceWorker();
start();
