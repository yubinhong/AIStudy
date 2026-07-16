import importlib.util
from pathlib import Path


def test_privacy_sanitizer_synthetic_eval_passes_without_provider_calls() -> None:
    path = Path(__file__).parents[3] / "evals/run_privacy_sanitizer_eval.py"
    spec = importlib.util.spec_from_file_location("study_privacy_sanitizer_eval", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.main() == 0
