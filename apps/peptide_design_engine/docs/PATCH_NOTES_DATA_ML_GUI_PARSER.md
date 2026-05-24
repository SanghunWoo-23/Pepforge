# Patch Notes — Data/ML GUI + AF3/PRODIGY Parser

## Added

### GUI Data/ML Tab 강화
- Training DB path selector
- Candidate mapping CSV selector/template generator
- Prepared CSV import button
- AF3 output folder parse → import button
- PRODIGY txt/csv/folder parse → import button
- Current `training_data.csv` preview table
- ML label column selector with DB-column refresh
- Train model button
- Model status display
- Open training DB button

### Parser
- `Python/external_parsers.py`
- AF3 JSON/CSV parser
- PRODIGY txt/out/log/csv parser
- Candidate ID/sequence/target matching via optional mapping CSV
- Canonical CSV export before append

### CLI
- `--parse-af3-folder`
- `--parse-prodigy`
- `--candidate-map`
- `--parsed-output-dir`

### Templates / samples
- `data/templates/candidate_mapping_template.csv`
- `data/sample_external_outputs/af3_output_example/`
- `data/sample_external_outputs/prodigy_output_example/`

## Preserved
- Existing Colab files
- Existing Python engine/CLI structure
- Existing data templates
- Existing example_results
- Existing desktop GUI/run/build scripts
- Existing Advanced JSON Override feature for full CONFIG retention

## Validation
- Python syntax compile: PASS
- CLI AF3 parse/import smoke test: PASS
- CLI PRODIGY parse/import smoke test: PASS
