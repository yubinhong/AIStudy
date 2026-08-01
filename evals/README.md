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

## English conversation safety evaluation

`run_english_conversation_safety_eval.py` checks the provider-neutral
`english-guided.v1` policy against fixed synthetic cases for personal
information requests, adult/dangerous topics, excessive replies and the
two-failure Chinese fallback. It does not record audio, call a Provider, or
contain child data:

```bash
services/api/.venv/bin/python evals/run_english_conversation_safety_eval.py
```

This is a framework safety gate, not a quality evaluation of a real speech
Provider. Any approved Provider requires a separate quality, latency, cost and
child-safety evaluation before the runtime lock can be opened.

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
and model-marker preflight. The amd64 release image may explicitly set
`STUDY_OCR_CONTAINER_RUNTIME=true` to accept its pinned Debian 13 runtime; this
does not relax the Linux, x86_64, Python, package, or model-marker checks. On
other hosts it exits with `blocked` and does not instantiate PaddleOCR.

## Self-hosted NewAPI live evaluation

`services/api/scripts/run_newapi_live_eval.py` is an environment-only check. It
generates one synthetic math PNG in memory, sends it through the real
PostgreSQL/MinIO/worker/NewAPI boundary, verifies the derivative is deleted,
and removes the task, Capture, job, extraction, idempotency, and audit rows it
created. It prints only stable status and extraction metadata; it never prints
the API key or raw Provider response. Run it only after explicitly setting
`STUDY_NEWAPI_ENABLED=true`:

```bash
docker compose -f infra/compose/compose.yml exec -T api \
  python scripts/run_newapi_live_eval.py
```

On 2026-07-16 the Ubuntu x86_64 environment completed this evaluation with
`gemini-3.1-flash-lite`: the job reached a `needs_confirmation=true`
Extraction, deleted the derivative, and left no synthetic Job record. The
adapter used `study-api/0.5` because Cloudflare rejected Python's default
`urllib` user-agent with error 1010. This is still not a real-child-data or
VerifiedQuestion confirmation test.
