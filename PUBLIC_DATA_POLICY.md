# Public Data Policy

Pepforge's public repository contains only source code, documentation, curated public-reference catalogs, empty import templates, synthetic examples, and automated tests.

## Never commit

- Company, customer, collaborator, or unpublished project records
- Real laboratory run history, operator names, LOT numbers, instrument exports, chromatograms, spectra, assay results, or synthesis notebooks
- Credentials, tokens, license keys, local configuration, or private endpoints
- User-trained models, serialized datasets, project sessions, runtime databases, logs, or generated result folders

## SPPS experimental evidence

The public `experimental_seed` directory is intentionally empty. `actual_runs.csv` contains only a header schema. Data entered through **Record Lab Data** or imported locally remain user-controlled runtime data and must be reviewed before any public commit.

Pepforge does not ship a synthetic pretrained PDE ranking model. Optional statistical-prior scoring requires an explicitly selected, human-reviewable CSV. User-trained model outputs are local artifacts and are ignored by Git.

The evidence advisor distinguishes `verified`, `parsed`, `incomplete`, and `excluded` records. These statuses describe data review state; they do not convert a record into scientific proof.

## Before publishing

1. Run `git status --ignored` and inspect every untracked file.
2. Search the complete tree for names, email addresses, internal identifiers, credentials, and unpublished sequences.
3. Confirm that SQLite databases, model files, sessions, projects, logs, and instrument outputs are absent.
4. Run the release gate and inspect the final ZIP contents before uploading.

If authorization is uncertain, do not publish the data.
