import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _module():
    path = Path(__file__).parents[3] / "evals/run_ocr_model_eval.py"
    spec = importlib.util.spec_from_file_location("study_ocr_model_eval", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_eval_generates_an_in_memory_png_and_only_matches_expected_terms() -> None:
    module = _module()

    capture = module._synthetic_capture("12 + 3 = 15")

    assert capture.metadata.format == "png"
    assert module._recognized((SimpleNamespace(text="12 + 3 = 15"),), ["12", "3", "15"]) is True
    assert module._recognized((SimpleNamespace(text="12 + 3 = 14"),), ["12", "3", "15"]) is False
    assert module._recognized((SimpleNamespace(text=r"\frac{1}{2}"),), ["1", "2"]) is True
