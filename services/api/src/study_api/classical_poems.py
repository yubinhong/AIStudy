"""Deterministic allowlist for public-domain classical poem evidence."""

from __future__ import annotations

CLASSICAL_POEM_CATALOG_VERSION = "classical-poem-catalog.v1"


def _normalize(value: str) -> str:
    return "".join(character for character in value.strip().lower() if character.isalnum())


def _normalize_title(value: str) -> str:
    return _normalize(value).removesuffix("节选")


_CLASSICAL_POEM_LINES: dict[str, tuple[str, ...]] = {
    "春晓": (
        "春眠不觉晓",
        "处处闻啼鸟",
        "夜来风雨声",
        "花落知多少",
    ),
    "咏鹅": (
        "鹅鹅鹅",
        "曲项向天歌",
        "白毛浮绿水",
        "红掌拨清波",
    ),
    "画": (
        "远看山有色",
        "近听水无声",
        "春去花还在",
        "人来鸟不惊",
    ),
    "悯农其二": (
        "锄禾日当午",
        "汗滴禾下土",
        "谁知盘中餐",
        "粒粒皆辛苦",
    ),
    "江南": (
        "江南可采莲",
        "莲叶何田田",
        "鱼戏莲叶间",
        "鱼戏莲叶东",
        "鱼戏莲叶西",
        "鱼戏莲叶南",
        "鱼戏莲叶北",
    ),
    "古朗月行": (
        "小时不识月",
        "呼作白玉盘",
        "又疑瑶台镜",
        "飞在青云端",
    ),
    "风": (
        "解落三秋叶",
        "能开二月花",
        "过江千尺浪",
        "入竹万竿斜",
    ),
}


def is_recognized_classical_poem(title: str, lines: tuple[str, ...]) -> bool:
    """Accept only an exact contiguous excerpt from a reviewed classical poem."""

    if len(lines) < 2:
        return False
    canonical = _CLASSICAL_POEM_LINES.get(_normalize_title(title))
    if canonical is None:
        return False
    normalized_lines = tuple(_normalize(line) for line in lines)
    if any(not line for line in normalized_lines):
        return False
    width = len(normalized_lines)
    return any(
        normalized_lines == canonical[start : start + width]
        for start in range(len(canonical) - width + 1)
    )
