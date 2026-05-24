SPPS LAST COUPLING / FINAL WASH UPDATE
======================================

This edition adds explicit last coupling step logic to the SPPS Planner.

Last Fmoc-AA coupling workflow:
1. Last Fmoc-AA coupling step
2. DMF wash x2
3. Final Fmoc deprotection
4. Final wash: DMF x3 and DCM x3
5. Optional MeOH wash x3 can be enabled by setting Final MeOH wash count to 3.

Final non-Fmoc Ac/chemical/label/modifier workflow:
1. Final chemical/modifier/label coupling
2. No Fmoc deprotection
3. Final wash: DMF x3 and DCM x3
4. Optional MeOH wash x3 can be enabled by setting Final MeOH wash count to 3.

Preserved logic:
- 2-CTC / trityl resin uses DCM swell/loading and no initial Fmoc deprotection.
- Wang / Rink Amide / amide-type resin is treated as Fmoc resin and includes initial deprotection.
- Ac is displayed as Ac, while material usage calculates Acetic anhydride (Ac2O; MW 102.09 g/mol; density 1.08 g/mL).
- Editable-table column widths remain as manually resized by the user. Reset occurs only when Reset column widths is clicked.
