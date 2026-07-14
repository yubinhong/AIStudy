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
