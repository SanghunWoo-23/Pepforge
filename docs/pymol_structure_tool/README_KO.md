# Pepforge PyMOL Structure Tool v1.3.0

**PyMOL 플러그인이 아니라**, modified peptide 구조를 만든 뒤 PyMOL에서 바로 여는 독립형 구조 생성기다.

## 목표

입력한 peptide/modification 문자열에서 다음을 모두 한 덩어리 3D starting structure로 만들고, PyMOL에서 `.pml`로 바로 띄운다.

- STD 20종 L-amino acid
- dA/dK/dF 등 D-form amino acid
- Aib, Nle, Orn, Dab, Cit, Hyp, Cha, Nal 등 non-natural AA
- Ahx, PEG4, PEG8, AEEA 등 linker/spacer
- Biotin, FITC, FAM, TAMRA, Cy5, NBD, DOTA 등 label
- Pal, Myr, Ste, Lau, Chol 등 chemical/lipid modification
- K(FITC), K(Ahx-Biotin), K(Pal), K(Chol), C(NBD) 같은 side-chain modification

## 기본 사용

```bash
python build_for_pymol.py "Ac-dK-Aib-LVFF-Ahx-Biotin-NH2" --name test --outdir outputs --confs 8
```

PyMOL에서는 생성된 PML을 실행한다.

```pymol
@outputs/test.pml
```

## Side-chain label / chemical 예시

```bash
python build_for_pymol.py "Ac-K(FITC)-LVFF-NH2" --name K_FITC_LVFF --outdir outputs
python build_for_pymol.py "Ac-K(Ahx-Biotin)-LVFF-NH2" --name K_Ahx_Biotin_LVFF --outdir outputs
python build_for_pymol.py "Ac-K(Pal)-LVFF-NH2" --name K_Pal_LVFF --outdir outputs
python build_for_pymol.py "Ac-K(Chol)-LVFF-NH2" --name K_Chol_LVFF --outdir outputs
```

## Batch 생성

```bash
python build_for_pymol.py --batch-csv examples/pepforge_batch_input_v130.csv --outdir outputs_batch --confs 4
```

PyMOL에서는:

```pymol
@outputs_batch/load_all_in_pymol.pml
```

## 검증 명령

```bash
python build_for_pymol.py --env
python build_for_pymol.py --tokens
python build_for_pymol.py --tokens chemical
python build_for_pymol.py --template-manifest
python build_for_pymol.py --audit-templates
python build_for_pymol.py "Ac-K(Chol)-LVFF-NH2" --parse-only
```

## v1.3.0에서 중요한 개선

- `chemical` category 추가: Pal/Myr/Ste/Lau/Chol/Mal/Dde
- `K(Pal)`, `K(Chol)` 같은 side-chain chemical modification 지원
- `data/templates/*.sdf` 전체 RDKit 읽기 검증 기능 추가
- `--audit-templates` 명령 추가
- PyMOL 색상에 chemical category 추가
- generated examples에 label/chemical/linker/non-natural/D-form 사례 포함

## 고정 해석 규칙

```text
STD AA = A C D E F G H I K L M N P Q R S T V W Y
dK/dF 등 = D-form STD AA
Aib/Nle/Orn/Dab/Cit/Hyp/Cha/Nal = non-natural AA
Ahx/PEG4/PEG8/AEEA/bAla/gAla = linker/spacer
Biotin/FITC/FAM/TAMRA/Cy5/NBD/DOTA = label/modification
Pal/Myr/Ste/Lau/Chol/Mal/Dde = chemical modification
Biotin, FITC, Pal, Chol은 sequence residue가 아니다.
```

## 한계

v1.3.0은 PyMOL에서 확인 가능한 **완전 연결 3D starting structure** 생성기다. RDKit/SMILES 기반으로 연결 구조를 만들고 template SDF를 검증하지만, label/chemical의 실제 실험적 conformer 또는 docking/MD-grade 구조를 보장하지 않는다. 논문용/도킹용 최종 구조는 curated SDF template, 추가 minimization, docking/MD 검증을 거쳐야 한다.

## v1.3.0 추가 핵심

이 버전은 PyMOL 플러그인이 아니라 독립형 builder 방향을 유지하면서, PyMOL에서 chemical/label/linker/non-natural/D/L AA가 붙은 구조를 더 명확히 확인하도록 개선했다.

- JSON에 `attach_point_map` 추가
- PML에서 attach atom을 sphere로 표시
  - blue = IN attach atom
  - red = OUT attach atom
- `data/template_manifest_v130.json/csv`에 local attach atom hint 기록
- `docs/ATTACH_POINT_MAPPING_KO.md` 추가

예시:

```bash
python build_for_pymol.py "Ac-K(Chol)-LVFF-NH2" --name K_Chol_LVFF --outdir outputs --confs 8
```

PyMOL:

```pymol
@outputs/K_Chol_LVFF.pml
```
