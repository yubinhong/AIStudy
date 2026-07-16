# AI evaluations

This directory contains fixed, repository-authored synthetic cases only. It
must not contain real child images, production prompts, credentials, raw model
responses, or copied textbook content.

## Current entrypoint

The OCR contract evaluation checks normalization before persistence:

```bash
cd services/api
./.venv/bin/python ../../evals/run_ocr_eval.py
```

It covers valid candidates, low-confidence correction, empty results, blank
line filtering, mismatched arrays, and control-character rejection. The runner
does not invoke PaddleOCR, MinIO, a network Provider, or an image file; its
output is a small aggregate report and records `provider_calls: false`.

Future evals must additionally cover tutor hint levels, refusal to directly
answer, schema failures, sensitive content, latency, and cost. New fixtures
must record source/authorization, grade, topic, expected behavior, and
forbidden behavior without containing child data.

The current provider-free Tutor Policy gate covers the safe offline fallback:

```bash
cd services/api
./.venv/bin/python ../../evals/run_tutor_policy_eval.py
```

It consumes only a synthetic `VerifiedQuestion`, returns levels 1–3, never
copies the verified answer, and reports `provider_calls: false`.

## Local privacy sanitization evaluation

`run_privacy_sanitizer_eval.py` runs six in-memory synthetic cases for region
masking, ordinary math content, low-confidence detections, ambiguous/large
faces, missing QR regions, and incomplete crops. It emits only aggregate
status, never image bytes or OCR text, and never calls a Provider:

```bash
cd services/api
./.venv/bin/python ../../evals/run_privacy_sanitizer_eval.py
```

## Locked CPU model smoke evaluation

`run_ocr_model_eval.py` generates four synthetic math images in memory and
uses the locked local text and on-demand `PP-FormulaNet_plus-M` CPU adapters.
It emits only aggregate case status and latency; it never accepts an image path
or stores raw OCR text:

```bash
cd services/api
PADDLE_MODEL_ROOT=/opt/study/models \
./.venv/bin/python ../../evals/run_ocr_model_eval.py
```

The command first requires the Ubuntu 24.04/x86_64/Python 3.12/Paddle version
and model-marker preflight. On other hosts it exits with `blocked` and does not
instantiate PaddleOCR.
