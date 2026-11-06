# Pepforge V6.0.0 — Release evidence and scientific limits

**Distribution:** Public research source release candidate; not an independently certified final scientific release.

| Item | Evidence status |
| --- | --- |
| SPPS Planner V8 Public launch contract | **3 passed / 0 failed**, recorded in integration source archive |
| Complete V6 project regression | Not established for this integrated package |
| Windows GUI, installer and EXE execution | Not independently verified |
| OpenFE/OpenMM real ABFE and modified-peptide production MD | Not independently verified |
| Boresch/MBAR correctness for arbitrary novel chemistry | Requires matched protocol and independent evidence |
| Independent experimental ΔG_bind accuracy | Not established |
| PyMOL full token panel | Source present; installed PyMOL UI requires manual verification |
| All D-form, noncanonical AA, linkers and tags | Not universally parameterized or validated |

### Evidence rule

A valid input parser, generated pose, numerical energy, test pass, and real experimental measurement are different evidence categories. Explicitly label prediction, simulation, parameterization and experimental validation separately. Do not present an internal docking score as ΔG_bind or Kd.

### Publication gate

Complete the [publication checklist](../PUBLICATION_CHECKLIST.md), audit the third-party SPPS V8 Public vendor license/redistribution obligations and confidential data, and capture a clean end-to-end install/GUI test on the actual release platform before publishing as a verified build.

## 통합 설치기 (2026-10-27)
- Windows/WSL2 통합 설치 메뉴 및 후속 실행 코드: 집중 소스 테스트 23건 통과(Windows 실기 구동·WSL2 다운로드 및 OpenFE 시뮬레이션 검증과 별개).
- Pepforge 고유 소스 무결성 감사에서 제3자/내장 SPPS V8 코드는 제외하며, SPPS V8 연결은 별도 계약 검사로 다룹니다. 제외는 SPPS V8 과학적 정확성이나 실기 검증을 의미하지 않습니다.

## 확대 회귀 검사 기록 (2026-10-27)
`python -m pytest -q --disable-warnings --maxfail=1`: 179 passed, 1 failed, 1 skipped. 미통과 항목은 `tests/test_v3_0_0_psb_spps_integration.py`의 구형 Docking Workbench 메뉴명에 대한 정확한 문자열 기대치 불일치입니다. 이번 연구용 공개본의 전체 회귀 통과를 주장하지 않습니다.

## Science Engine WSL bootstrap refinement (2026-10-27)
- On explicit install selection, missing Ubuntu triggers `wsl --install -d Ubuntu` attempt; restart/UAC/first-run setup is surfaced as **incomplete**, never falsely marked success.
- Installed Ubuntu is selected by distribution name rather than assuming the WSL default.
- Missing Linux Miniforge is bootstrapped with an official SHA-256-pinned installer; conda-forge `pepforge-science` creation/update and import/CLI checks follow.
- Verify-only performs no OS, manager or package installation.
- Tests mock WSL/Conda and network; **native Windows WSL provisioning and actual package downloads remain untested** in this environment.

- Additional **37/37 offline focused installer/SPPS tests passed**. A new broader pytest attempt reached ~17% before execution timeout; it is **not** a completed full regression.

## GitHub packaging audit refresh (2026-10-27)

- Corrected current user manuals and legacy SPPS package READMEs that advertised Pepforge V5 / SPPS V7 despite the V6 + V8 integrated source.
- Normalized version comparison in the release gate, release-verify and full-package audit: `VERSION.txt` uses public display `V6.0.0`, code metadata uses `6.0.0`.
- Focused release/installer/SPPS tests: **42 passed / 0 failed**.
- Release Gate: **25 passed / 0 failed**; compiled **779** Python files, **0 errors**.
- Full suite attempted but did not finish: **NOT certified**. Actual Windows/WSL2 package installation and scientific ABFE accuracy likewise **not verified**.
- Static checks are about source packaging only and cannot establish security, licensing, experimental affinity or performance.

## Windows-integrated V8 workspace (2026-10-28)

- Original V8 UI rendered within Pepforge launcher via native cross-process Win32 parenting, with isolated SPPS process and fallback standalone launch.
- The updated V8 Public chemistry engine is byte-identical to the supplied 2026-10-28 original (`sha256: 5cf59ad71ea1637df4768d812612a86635b31c691efc153f93ef328d736108de`).
- Unit/contract and Xvfb Tk launcher navigation validated. **Actual Windows SetParent + DPI + installed EXE acceptance remains NOT TESTED.**
- Native docking and ABFE scientific validation remain separate, unfinished requirements.

## Current UI / SPPS policy (2026-10-29)

- Studio Docking tab groups Receptor (PDB and Sequence), Peptide (PDB and Sequence), and Docking controls separately. Peptide sequence is shared across the Studio tabs.
- V8 opens as a normal **separate** desktop window from Pepforge; Windows `SetParent` embedding is retired. Previous 2026-10-28 entries are historical.
- Installer/Windows EXE, complete project regression, and scientific OpenFE accuracy require independent target-platform and data validation.
