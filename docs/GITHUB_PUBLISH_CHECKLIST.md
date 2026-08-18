# GitHub Publish Checklist

Before creating a public release:

- [ ] `VERSION.txt` matches the release tag.
- [ ] `README.md` and `README_KO.md` describe the actual build.
- [ ] `CHANGELOG.md` contains the release changes.
- [ ] `CITATION.cff` contains the same version.
- [ ] License/citation wording does not contain stale version numbers.
- [ ] No build caches, local workspaces, output folders, secrets, or personal datasets are committed.
- [ ] `PUBLIC_DATA_POLICY.md` review confirms no company/laboratory history, SQLite database, user model, session, or instrument export is included.
- [ ] `apps/spps_planner_app/data/actual_runs.csv` and `experimental_seed/` contain schema/readme content only.
- [ ] No synthetic pretrained-lite PDE model or training table is included.
- [ ] `python -m compileall -q .` passes.
- [ ] Relevant automated tests pass.
- [ ] Main GUI opens from source.
- [ ] Changed GUI workflows pass an end-to-end smoke test.
- [ ] Windows build is tested before attaching an installer as a Release asset.
- [ ] Scientific claims in release notes stay inside the documented claim boundary.
- [ ] Installer/EXE is uploaded to GitHub Releases rather than committed into source history.
- [ ] Final source ZIP contents and SHA-256 are recorded in the GitHub Release.
