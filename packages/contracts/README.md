# Contracts

This directory is the single source for the public OpenAPI contract and AI JSON
Schemas. Generated client SDKs belong in build output directories and are not
hand-maintained in application code.

The current contract includes the P0 health endpoint, the synthetic
household/child/device vertical slice, Capture upload/correction/save/delete
paths, and a local/CI-only parent child-profile deletion path that requires
Capture object cascade success before removing the profile. The demo principal headers are
local/CI only and must be replaced by the approved authentication adapter
before any staging or production use.

Domain types are not hand-maintained in Web or Flutter. SDK generation remains
the subject of `docs/adr/0002-openapi-contract-and-sdk-generation.md`.
