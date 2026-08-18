# Scientific Scope and Validation Boundary

## Purpose

Pepforge is designed for peptide research workflow integration: candidate generation, synthesis planning, conformational preparation, screening-level interaction analysis, and preparation for external validation.

It is not an experimental instrument and it does not make measured physical quantities appear from computation.

## Structure Builder

### What it does
- generates multiple peptide conformers
- preserves and interprets an ensemble
- calculates backbone φ/ψ geometry where available
- classifies candidate conformers into broad structural families
- supports canonical peptide search seeds for important backbone basins
- exports structures and analysis tables for downstream review

### What it does not prove
- one unique native/in-vivo conformation
- thermodynamic equilibrium populations
- experimental secondary-structure fractions
- publication-grade free-energy surfaces

`family_fraction_of_generated_ensemble` describes the generated search ensemble only. It is not an equilibrium population.

## Docking Workbench

Pepforge's internal workbench performs docking-oriented screening/contact analysis for prioritization. Scores and contacts are model-dependent screening outputs.

It does not replace dedicated docking engines or experimental affinity measurement.

Do not interpret internal screening values as measured Kd or binding proof.

## External MD / docking

Pepforge may create preparation packages, hand-off files, and import/organization workflows for external software.

Actual Vina/GROMACS/etc. computation requires those external programs and suitable scientific setup.

## Modified / non-natural peptides

Modified peptides are a central Pepforge use case, but force-field and conformational evidence coverage varies greatly among building blocks.

Evidence policy:

```text
A  direct experimental structural evidence
B  structural/statistical evidence
C  validated computational/force-field parameterization
D  closest-analogue estimate, explicitly labelled
U  unsupported / unavailable
```

Pepforge should not silently convert `U` into a made-up numerical propensity.

## Experimental validation

Where claims matter scientifically, consider orthogonal validation such as:

- CD / NMR / crystallography or other structure-sensitive measurements
- binding assays appropriate to the system
- independent docking engine comparison
- all-atom MD with appropriate force field and parameterization
- synthesis / analytical confirmation of peptide identity and purity

The correct validation method depends on the research question.
