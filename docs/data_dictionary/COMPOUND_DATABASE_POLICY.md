# Compound Database and Token Policy - v2.0.0

## Database file

```text
apps/spps_planner_app/data/compounds.csv
```

## Summary

- Active token count: 212
- Manual-required active tokens: 38
- Active tokens with blank reagent MW: 85
- Active tokens with blank product contribution: 37

Blank values are not automatically errors. They are used when exact vendor form is required for correct calculation.

## Key columns

| Column | Meaning |
|---|---|
| Token | user-facing token or internal normalized token |
| Class | AA, non-natural AA, linker, label, tag, modifier, solvent, etc. |
| Reagent/protected form | actual or representative reagent form |
| Reagent MW (g/mol) | mass used for material usage calculation |
| Product MW contribution (g/mol) | mass contribution to final peptide product |
| Counts as coupling unit? | whether it contributes to coupling/material rows |
| Terminal/control only? | whether it acts only as terminal/control token |
| Chemistry profile | default reaction-policy grouping |
| Applied reagent logic | how the planner uses the row |
| DB note | manual-required and caution notes |

## Policy

1. Reagent MW and product contribution are separate fields.
2. Density is applied only to liquid reagents.
3. Solid reagents should not receive density values.
4. Generic vendor-dependent labels should be manual-required.
5. Form-specific rows are preferred for activated dyes and chelators.
6. Linkers are handled as amino-acid-like units when appropriate.
7. Labels/tags/caps/terminal chemicals are chemical modifier units.

## Examples

| Token | Interpretation |
|---|---|
| Ac | acetic anhydride reagent; acetyl product contribution |
| Caf | caffeic acid reagent; caffeoyl contribution |
| Gal | gallic acid/galloyl-type modifier |
| Pal | palmitic acid/palmitoyl terminal lipid cap |
| Ahx | amino-acid-like linker unit |
| FITC/FAM/TAMRA/CY dyes | require form-specific verification unless explicit row exists |
