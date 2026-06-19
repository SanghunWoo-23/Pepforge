# Chemical / label 지원 규칙

## Label
Biotin, FITC, FAM, TAMRA, Cy5, NBD, DOTA는 sequence residue가 아니라 label/modification이다.

예:

```text
Ac-K(FITC)-LVFF-NH2
Ac-K(Ahx-Biotin)-LVFF-NH2
Cy5-PEG4-RGD-NH2
```

## Chemical
Pal, Myr, Ste, Lau, Chol, Mal, Dde는 chemical modification이다. peptide sequence residue가 아니다.

예:

```text
Ac-K(Pal)-LVFF-NH2
Ac-K(Chol)-LVFF-NH2
```

## Linker
Ahx, PEG4, PEG8, AEEA, bAla, gAla는 linker/spacer이다. STD AA가 아니다.
