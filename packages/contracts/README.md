# Contracts

This directory is the single source for the public OpenAPI contract and AI JSON
Schemas. Generated client SDKs belong in build output directories and are not
hand-maintained in application code.

The current `0.8.0` contract includes the P0 health endpoint, the synthetic
household/child/device vertical slice, Capture upload/correction/save/delete,
local/CI OCR enqueue/result-read/confirmation paths, and a local/CI-only parent child-profile deletion path that requires
Capture object cascade success before removing the profile. Every Household
business endpoint now declares only the approved revocable SessionCookie or
BearerSession transports; HMAC and demo-principal schemes have been removed.
It also includes active-session resume, server-trusted Tutor turns, learning
session completion, weekly report aggregation, and short-lived child data
export snapshots.

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

Domain types are not hand-maintained in Web or Flutter. SDK generation remains
the subject of `docs/adr/0002-openapi-contract-and-sdk-generation.md`.
