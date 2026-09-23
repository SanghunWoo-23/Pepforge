# SPPS Planner V5 Evidence Workflow (legacy document path)

Pepforge V4.0.0 embeds the Public/Data-Sanitized SPPS Planner V5.0.0 single-plan workflow. This filename is retained only for backward documentation links. LOT Number and Batch Manager are excluded from the Pepforge operator surface.

## Planning flow

1. Enter a peptide sequence and review parsed residues, terminal chemistry, tags, linkers, and warnings.
2. Set resin, scale, loading, coupling chemistry, loading time, and cleavage time.
3. Use **Generate / Update** to create Plan, Materials, Total Materials, Checklist, and cleavage output.
4. Review table edits and use **Apply Change** to commit them explicitly.
5. Export the plan together with warnings, evidence status, and literature guidance.

## Evidence states

| State | Meaning | Automatic use |
| --- | --- | --- |
| `verified` | Operator-reviewed record with sufficient fields | May support exact-condition Apply |
| `parsed` | Imported/interpreted record awaiting review | Evidence only unless explicitly confirmed by the supported UI route |
| `incomplete` | Required fields or components are missing | Apply blocked |
| `excluded` | Record intentionally omitted from advice/training | Not used |

## Recommendation safety

- Loading Apply uses one exact resin + amino-acid historical condition.
- Coupling advice transfers one reviewed successful condition; repeated identical conditions can form consensus.
- Cleavage is driven by the current sequence, not the product label.
- One historical record supplies one whole cocktail. Components are never mixed across records.
- Unknown or unparsed cocktail components block exact-record Apply.
- A fitted model can summarize evidence but cannot supply an invented optimum for Apply.
- Loading and cleavage time do not alter calculated stoichiometric amounts.

## Exact-condition contract

The current embedded SPPS V5 workflow is evidence-first. Exact cleavage conditions are not hard-coded to a named peptide. When a complete reviewed historical record is compatible with the current sequence/context, the advisor may reproduce that single record as one coherent condition. Generic chemistry rules remain advisory when compatible history is absent and do not create an exact historical cocktail or enable exact-condition Apply. Imported records are not automatically promoted to `verified`.

All outputs remain planning aids. Local SOPs, SDS requirements, resin behavior, reagent quality, instrument dead volume, reaction monitoring, and experimental verification remain the user's responsibility.
