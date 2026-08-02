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

test("Figma pilot is limited to the five review champions", () => {
  assert.match(
    appSource,
    /const FIGMA_PILOT_SLUGS = new Set\(\[\s*"vayne",\s*"graves",\s*"yunara",\s*"lillia",\s*"yasuo",?\s*\]\)/,
  );
});

test("pilot detail uses the confirmed Figma poster structure", () => {
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
