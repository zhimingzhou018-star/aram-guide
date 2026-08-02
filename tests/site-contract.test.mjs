import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const appSource = await readFile(new URL("../app.js", import.meta.url), "utf8");
const htmlSource = await readFile(new URL("../index.html", import.meta.url), "utf8");

test("home loads the lightweight index and detail loads one hero JSON", () => {
  assert.match(appSource, /fetch\("\.\/data\/index\.json/);
  assert.match(appSource, /fetch\(`\.\/data\/heroes\/\$\{encodeURIComponent\(slug\)\}\.json/);
  assert.doesNotMatch(htmlSource, /data\/guides\.json/);
});

test("search covers names, titles, English IDs and aliases", () => {
  assert.match(appSource, /guide\.name/);
  assert.match(appSource, /guide\.title/);
  assert.match(appSource, /guide\.riotId/);
  assert.match(appSource, /guide\.aliases/);
});

test("detail is composed from the required guide modules", () => {
  for (const component of [
    "HeroHeader",
    "SpellAndSkillModule",
    "ItemModule",
    "AugmentTierModule",
    "AugmentCombinationModule",
    "GameplayModule",
    "LegacyPosterFallback",
  ]) {
    assert.match(appSource, new RegExp(`function ${component}\\(`));
  }
});

test("detail keeps a home control and removes poster actions", () => {
  assert.match(appSource, /返回首页/);
  assert.doesNotMatch(appSource, /查看原图|下载原图|分享攻略/);
});

test("confirmed Figma detail is enabled for every champion", () => {
  assert.doesNotMatch(appSource, /FIGMA_PILOT_SLUGS/);
  assert.match(appSource, /app\.innerHTML = `<section class="detail-shell figma-detail-shell">\$\{FigmaGuidePage\(guide, selectedGuide\.build\.key\)\}<\/section>`/);
});

test("all detail pages use the confirmed Figma poster structure", () => {
  assert.match(appSource, /function FigmaGuidePage\(/);
  for (const className of [
    "figma-poster",
    "figma-hero-header",
    "figma-build-strip",
    "figma-gameplay",
    "figma-items",
    "figma-augment-tier",
    "figma-combinations",
  ]) {
    assert.match(appSource, new RegExp(className));
  }
});

test("detail exposes every build as a visible win-rate tab", () => {
  assert.match(appSource, /guide\.builds/);
  assert.match(appSource, /figma-build-tab/);
  assert.match(appSource, /figma-build-stat/);
  assert.match(appSource, /coreProfile/);
  assert.match(appSource, /aria-pressed/);
  assert.match(appSource, /aria-label="\$\{escapeHtml\(build\.name\)\}，胜率/);
  assert.doesNotMatch(appSource, /点击切换|流派 01/);
});
