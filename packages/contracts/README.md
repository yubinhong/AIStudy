# Contracts

This directory is the single source for the public OpenAPI contract and AI JSON
Schemas. Generated client SDKs belong in build output directories and are not
hand-maintained in application code.

The current local `0.14.0` contract includes the P0 health endpoint, the synthetic
household/child/device vertical slice, Capture upload/correction/save/delete,
local/CI OCR enqueue/result-read/confirmation paths, and a local/CI-only parent child-profile deletion path that requires
Capture object cascade success before removing the profile. Every Household
business endpoint now declares only the approved revocable SessionCookie or
BearerSession transports; HMAC and demo-principal schemes have been removed.
It also includes active-session resume, server-trusted Tutor turns, learning
session completion, weekly report aggregation, and short-lived child data
export snapshots.

Parent learning details accept an optional timezone-aware half-open interval.
The default is the latest 30 days, one request is capped at 31 days and 500
rows, and requests outside the 180-day detailed-history window are rejected.

Curriculum PDF contracts also expose authenticated private page images and
parent-reviewed whole-book knowledge maps. They never expose a MinIO object key,
storage URL, or presigned upload URL.

The curriculum contract is PDF-only for binary uploads. Multiple PDFs up to
50 MiB each enter a private reviewable draft and are parsed by the local bounded
worker; scanned PDFs are marked `needs_ocr`. Parents can idempotently delete an
uploaded source together with derived parsing facts. A parent-only page reader
returns a reviewed snapshot's page number, display title, parsed text and
confidence for the owning child; it never returns the original PDF, object key
or object-storage URL. Mistake closeout, evidence-backed review attempts,
page-scoped curriculum sources, and Tutor hint progression metadata are part of
the `0.9.x` contract.

Capture upload is a single authenticated API stream. The contract does not
expose presigned URLs, object keys, or a separate upload-confirmation operation;
the matching API and Flutter implementation are locally verified. The Ubuntu
deployment must be upgraded as a pair before its old runtime contract is
considered migrated.

Provider-neutral ADR-0015 schemas are versioned under `schemas/`: local
privacy-sanitization metadata, image-analysis job state, unverified question
extraction/record, human-verified question, and the provider-free
`tutor-hint.v1` response. The self-hosted NewAPI adapter may create an
unverified extraction only after the confirmed derivative hash gate; the
offline Tutor Policy remains a local zero-cost fallback and never returns a
direct answer.

ADR-0027 makes `ChildProfile.subjects` and curriculum material/snapshot records
explicitly support `math` and `chinese`, with old curriculum rows migrated to
`math`. Chinese content and attempt endpoints expose versioned prompts and
scores but never expose the server-side `AnswerSpec`; additive child exports
include Chinese attempts and review state. Chinese curriculum analysis remains
blocked until its subject-specific schema and prompt exist.

ADR-0025 adds a separately gated English speaking plugin. English remains after
Chinese in the product sequence and keeps its independent consent and provider
gate rather than entering the deterministic Chinese scoring model.
English live control events are provider-neutral JSON Schema documents; binary
frames are mono PCM16 little-endian at 16 kHz input and 24 kHz output. The
public contract contains no cloud key, provider URL, raw audio, transcript, or
provider message. Runtime defaults remain globally disabled.

Domain types are not hand-maintained in Web or Flutter. SDK generation remains
the subject of `docs/adr/0002-openapi-contract-and-sdk-generation.md`.
