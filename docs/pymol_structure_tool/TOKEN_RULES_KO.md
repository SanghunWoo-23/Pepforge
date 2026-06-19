# Token Rules

## 절대 고정 규칙

- STD는 canonical 20 amino acids만 의미한다.
- `dX`는 X의 D-form이다.
- Biotin/FITC/FAM/TAMRA/Cy5/NBD/DOTA는 label/modification이다.
- Ahx/PEG4/PEG8/AEEA/bAla/gAla는 linker/spacer이다.
- Aib/Nle/Orn/Dab/Cit/Hyp/Cha/Nal은 non-natural AA이다.
- tag는 sequence로 확장된다. 예: His6 → HHHHHH.

## 권장 입력

명확성을 위해 multi-letter token은 `-`로 구분하거나 bracket을 쓸 수 있다.

```text
Ac-dK-Aib-LVFF-Ahx-Biotin-NH2
[Ac]-[dK]-[Aib]-L-V-F-F-[Ahx]-[Biotin]-[NH2]
```
