"""Run deterministic English conversation policy safety cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

API_SRC = Path(__file__).resolve().parents[1] / "services" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from study_api.english_practice import EnglishConversationPolicy, EnglishLevel  # noqa: E402


def main() -> int:
    fixture_path = (
        Path(__file__).parent / "fixtures" / "english_conversation_safety_v1.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    policy = EnglishConversationPolicy()
    instruction = policy.instruction("greetings", EnglishLevel.PRE_A1)
    required_boundaries = (
        "short English",
        "two consecutive",
        "personal information",
        "Refuse adult, dangerous, and unrelated free-chat",
        "Do not use search, tools, video",
        "under 40 words",
    )
    assert all(boundary in instruction for boundary in required_boundaries)

    passed = 0
    for case in fixture["cases"]:
        decision = policy.evaluate_reply(
            case["reply"],
            consecutive_failures=case.get("consecutive_failures", 0),
        )
        assert decision.allowed is case["expected_allowed"], case["id"]
        assert decision.reason == case["expected_reason"], case["id"]
        assert decision.use_chinese_fallback is case.get(
            "expected_chinese_fallback", False
        ), case["id"]
        passed += 1
    print(f"english conversation safety eval: {passed}/{len(fixture['cases'])} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
