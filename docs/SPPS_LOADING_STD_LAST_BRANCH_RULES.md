# SPPS Loading, Standard Cycle, Last Coupling, and Branch Rules

This edition separates resin swell/loading, standard Fmoc cycles, last coupling, final modifier coupling, and branch synthesis blocks.

## Resin swell and loading

- 2-CTC / trityl resin: DCM swell and DCM-family loading. Initial Fmoc deprotection is not scheduled because the resin itself does not carry an Fmoc handle.
- Amide / Rink / Wang-type Fmoc resin: DMF swell/loading-family handling. Initial Fmoc deprotection is retained before the first coupling when appropriate.

## Standard non-final Fmoc-AA cycle

1. Deprotection x2
2. DMF wash x6
3. Coupling
4. DMF wash x2

## Last Fmoc-AA coupling

1. Deprotection x2
2. DMF wash x6
3. Coupling
4. Final deprotection x2
5. DMF wash x3
6. DCM wash x3
7. Optional MeOH wash x3, if enabled

## Final Ac / chemical / label / modifier

These rows do not require post-coupling Fmoc deprotection because they are not Fmoc-AA additions. If the previous chain terminus is Fmoc-protected, Pepforge schedules pre-reaction deprotection and DMF washing before the final modifier coupling.

## Branch mode

Branch mode appends side-chain workflow rows after the linear plan:

1. Branch protecting group removal
2. Branch arm coupling rows in C-term to N-term direction
3. Fmoc-cycle logic for branch arm rows after the first side-chain coupling
4. Final deprotection/wash logic at the end of the branch arm when applicable
