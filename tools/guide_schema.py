"""Validation contract for modular hero guide payloads."""

from __future__ import annotations

import re
from typing import Any


class ValidationError(ValueError):
    """Raised when a guide cannot be safely published."""


def require_mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValidationError(f"{key} 必须是对象")
    return value


def require_text(mapping: dict[str, Any], key: str, path: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if not value:
        raise ValidationError(f"{path}.{key} 不能为空")
    if value.isdigit():
        raise ValidationError(f"{path}.{key} 不得使用纯数字显示名")
    return value


def require_named_entries(value: Any, expected: int, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != expected:
        raise ValidationError(f"{path} 必须包含 {expected} 项")
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise ValidationError(f"{path}[{index}] 必须是对象")
        if row.get("id") is None:
            raise ValidationError(f"{path}[{index}].id 不能为空")
        require_text(row, "name", f"{path}[{index}]")
    return value


def validate_guide(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValidationError("攻略必须是对象")
    if payload.get("schemaVersion") != 2:
        raise ValidationError("schemaVersion 必须为 2")

    hero = require_mapping(payload, "hero")
    if not isinstance(hero.get("id"), int):
        raise ValidationError("hero.id 必须是整数")
    for key in ("slug", "riotId", "name", "title"):
        require_text(hero, key, "hero")
    aliases = hero.get("aliases")
    if not isinstance(aliases, list) or not aliases:
        raise ValidationError("hero.aliases 不能为空")

    require_mapping(payload, "ranking")
    build = require_mapping(payload, "build")
    require_text(build, "key", "build")
    require_text(build, "name", "build")
    require_named_entries(payload.get("summonerSpells"), 2, "summonerSpells")

    skill_order = str(payload.get("skillOrder", ""))
    parts = skill_order.split(">")
    if not re.fullmatch(r"[QWER]>[QWER]>[QWER]", skill_order) or len(set(parts)) != 3:
        raise ValidationError("skillOrder 必须是三个不重复技能的加点顺序")

    items = require_mapping(payload, "items")
    starter = items.get("starter")
    if not isinstance(starter, list) or not 1 <= len(starter) <= 2:
        raise ValidationError("items.starter 必须包含 1–2 项")
    for index, row in enumerate(starter):
        if not isinstance(row, dict) or row.get("id") is None:
            raise ValidationError(f"items.starter[{index}] 缺少 id")
        require_text(row, "name", f"items.starter[{index}]")
    require_named_entries(items.get("core"), 3, "items.core")
    require_named_entries(items.get("recommended"), 6, "items.recommended")

    augments = require_mapping(payload, "augments")
    for rarity in ("prismatic", "gold", "silver"):
        require_named_entries(augments.get(rarity), 6, f"augments.{rarity}")
    combinations = augments.get("combinations")
    if not isinstance(combinations, list) or len(combinations) != 4:
        raise ValidationError("augments.combinations 必须包含 4 项")
    for index, combination in enumerate(combinations):
        if not isinstance(combination, dict):
            raise ValidationError(f"augments.combinations[{index}] 必须是对象")
        names = combination.get("names")
        if not isinstance(names, list) or len(names) < 2:
            raise ValidationError(f"augments.combinations[{index}].names 至少包含 2 项")
        for name in names:
            text = str(name).strip()
            if not text or text.isdigit():
                raise ValidationError("海克斯组合不得使用空名称或纯数字显示名")

    gameplay = require_mapping(payload, "gameplay")
    if gameplay.get("status") != "reviewed" or gameplay.get("locked") is not True:
        raise ValidationError("gameplay 必须经过审核并锁定")
    summary = gameplay.get("summary")
    if not isinstance(summary, list) or len(summary) != 3 or not all(str(line).strip() for line in summary):
        raise ValidationError("gameplay.summary 必须包含 3 条有效摘要")

    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValidationError("sources 不能为空")
    aramkit = next((source for source in sources if source.get("provider") == "ARAMKit"), None)
    if not aramkit:
        raise ValidationError("sources 必须包含 ARAMKit")
    for key in ("version", "dataDate", "region", "dataLevel"):
        require_text(aramkit, key, "sources.ARAMKit")
    if aramkit["region"] != "unknown" or aramkit["dataLevel"] != "aggregate":
        raise ValidationError("ARAMKit 来源必须标记为 unknown / aggregate")

