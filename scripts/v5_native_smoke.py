from __future__ import annotations

"""Native-backend smoke checker for Pepforge V5 RC1.

This script never substitutes mock scientific output for missing engines.  It is
safe to run from a fresh unzip to record which optional V5 backends are truly
available on the current machine.
"""

import argparse
import json
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from peptiforg_core.psb_v5_full_pipeline import backend_status
from peptiforg_core.structure_predictor_backends import detect_alphafold3


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="")
    p.add_argument("--af3-run-script", default="")
    p.add_argument("--af3-model-dir", default="")
    p.add_argument("--af3-db-dir", default="")
    args = p.parse_args(argv)

    payload = backend_status()
    if args.af3_run_script or args.af3_model_dir or args.af3_db_dir:
        payload["structure_predictors"]["alphafold3"] = detect_alphafold3(
            args.af3_run_script or None,
            model_dir=args.af3_model_dir or None,
            db_dir=args.af3_db_dir or None,
        )
    payload["claim_guard"] = (
        "READY means the adapter found its required runtime/configuration on this machine. "
        "It is not evidence that a scientific benchmark has completed."
    )
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        out = Path(args.output).expanduser().resolve(); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(out)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
