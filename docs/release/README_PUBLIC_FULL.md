# Pepforge

**Pepforge** is an integrated peptide workflow suite for sequence hotspot analysis, constraint-aware peptide candidate design, and SPPS-oriented synthesis planning.

Pepforge is organized as a practical research software package rather than a single-purpose script. It supports independent use of each module and connected workflow use across modules.

## Modules

1. **Hot Spot Finder**  
   Identifies candidate hotspot regions from sequence input and exports only the calculated hotspot table intended for downstream design.

2. **Peptide Design Engine**  
   Generates and ranks peptide candidates under configurable sequence, chemistry, linker, motif, bridge, diversity, and ML-prior options.

3. **SPPS Planner**  
   Converts peptide notation such as `Ac-EEMQRR-NH2` into an editable C-terminal-to-N-terminal synthesis planning table. The planner supports manual control of equivalents, coupling systems, catalysts/additives, bases, solvents, deprotection conditions, repeat counts, material usage, and printable checklist output.

## Intended Workflow

```text
Input sequence
  -> Hot Spot Finder
  -> Peptide Design Engine
  -> SPPS Planner
  -> CSV/XLSX export and ML-ready synthesis log
```

Each module can also be used independently.

## Installation Builder

Open the `Pepforge` folder and run:

```bat
INSTALL_BUILD_TOOLS_AND_BUILD.bat
```

The final installer is generated at:

```text
installer\output\Pepforge_Setup_v0.1.0.exe
```

Before the build is run, it is normal for `installer\output` to contain only a placeholder guide or to be empty.

After installation, the default program location is:

```text
C:\Users\<USER>\AppData\Local\Programs\Pepforge
```

The desktop shortcut task is enabled by default in the installer.

## Outputs

- hotspot-only CSV result
- peptide design full results and selected candidates
- editable SPPS plan CSV
- material usage CSV
- printable synthesis checklist CSV
- ML-ready SPPS log CSV
- SPPS XLSX workbook

## Scientific Positioning

Pepforge is a research-support tool. It does not guarantee binding, biological activity, synthesis success, or experimental reproducibility. All peptide candidates, hotspot outputs, and SPPS plans must be reviewed by qualified users and validated experimentally when required.
