from study_api.classical_poems import (
    CLASSICAL_POEM_CATALOG_VERSION,
    is_recognized_classical_poem,
)


def test_classical_poem_gate_rejects_nursery_rhyme() -> None:
    assert CLASSICAL_POEM_CATALOG_VERSION == "classical-poem-catalog.v1"
    assert not is_recognized_classical_poem(
        "剪窗花",
        (
            "小剪刀，手中拿，",
            "我学奶奶剪窗花。",
            "剪雪花，剪梅花，",
        ),
    )


def test_classical_poem_gate_accepts_exact_contiguous_lines_after_normalization() -> None:
    assert is_recognized_classical_poem(
        "风",
        (
            "解 落 三 秋 叶 ，",
            "能 开 二 月 花 。",
            "过 江 千 尺 浪 ，",
            "入 竹 万 竿 斜 。",
        ),
    )
    assert is_recognized_classical_poem(
        "古朗月行（节选）",
        ("小时不识月，", "呼作白玉盘。"),
    )
    assert not is_recognized_classical_poem(
        "风",
        ("解落三秋叶", "错误的下一句"),
    )
