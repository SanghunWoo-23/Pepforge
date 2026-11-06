# Public Data Policy

SPPS Planner has separate **Public** and **Private/Internal** build ancestry.

## Public repository

The public repository may contain:

- application source code;
- tests and verification tools;
- empty/example-compatible data structures;
- documentation required to build and use the software.

It must not contain:

- company experimental history or private seed datasets;
- company-local SQLite databases;
- original laboratory photographs;
- confidential peptide/sample names or sequences;
- private manifests, provenance files, internal notes, or model artifacts;
- user-created runtime recipe/project files.

The public experimental seed directory is intentionally empty except for explanatory documentation.

## Local runtime data

Projects, experimental records, preferences, and My recipes are stored in user-writable runtime locations. They are not intended to be committed to the repository.

Before publishing a release, check that runtime output, local DB files, caches, and user recipe files are absent.

## Private build

Private/Internal builds may contain organization-specific experimental assets. They must remain outside the public repository and must not be recreated by copying private data into a Public package.

## Release verification

Use the included release/integrity tools before publication. They include checks intended to preserve the Public/Private boundary and release hygiene.
