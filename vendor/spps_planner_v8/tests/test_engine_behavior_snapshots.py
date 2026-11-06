from __future__ import annotations

import hashlib
import json
import math

import pandas as pd

from spps_planner.engine import (
    PlanInput,
    generate_cleavage_cocktail,
    generate_detailed_operations,
    generate_materials,
    generate_step_materials,
    generate_step_matrix,
    generate_step_reagent_plan,
    plan_summary,
    validate_plan,
)


def _normal(value):
    if value is None or isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, float):
        return round(value, 9)
    return value


def _digest(value) -> str:
    if isinstance(value, pd.DataFrame):
        value = [
            [str(column) for column in value.columns],
            [[_normal(cell) for cell in row] for row in value.itertuples(index=False, name=None)],
        ]
    elif isinstance(value, dict):
        value = {str(key): _normal(item) for key, item in sorted(value.items())}
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


SCENARIOS = {
    "amide": PlanInput(
        sequence="Ac-AAAAAA-NH2",
        scale_mmol=0.4,
        resin="Rink Amide AM",
        resin_loading_mmol_g=0.8,
    ),
    "ctc": PlanInput(
        sequence="AEKIRKELEKQ",
        scale_mmol=0.2,
        resin="CTC(합성기)",
        resin_loading_mmol_g=1.39,
        apply_resin_loading=False,
        default_coupling_reagent="HBTU",
        default_reagent_eq=10,
        default_catalyst="",
        default_catalyst_eq=0,
        default_base="DIEA",
        default_base_eq=5,
        default_reaction_solvent="NMP",
    ),
    "branch": PlanInput(
        sequence="Ac-G-H-K-K-K(GGEP)-NH2",
        scale_mmol=0.4,
        resin="Rink Amide AM",
    ),
}

GENERATORS = {
    "step_matrix": generate_step_matrix,
    "operations": generate_detailed_operations,
    "reagent_plan": generate_step_reagent_plan,
    "step_materials": generate_step_materials,
    "materials": generate_materials,
    "cleavage": generate_cleavage_cocktail,
    "validation": validate_plan,
    "summary": plan_summary,
}

EXPECTED = {
    "amide": {
        "step_matrix": "a8ec4ed62996759057b94182875568e13f57169d7f1b9800fbb1c0d20318685e",
        "operations": "9454579738776ae65dd9785f553c4c58b72aa80ec4cdea30532ef77c0413cff7",
        "reagent_plan": "834729cf11e012dc98121bfda830763e2e65b37bbe4fb6ffbd412e15fe0b7a55",
        "step_materials": "56034e1023b8975fa3573b6d142fde6dc1cc2c9aa7c138ed6ff1e68d75f63b78",
        "materials": "ead819db9a332e1d0d111e5f1913291ae4ec1dc16ca5c32feb951730d91c5fb8",
        "cleavage": "fef6150fbbdd7817dfb3235ab607846e6dce0d4b0fd0128e7b10399281c754f2",
        "validation": "1a5ba0512c1795213d2534c8a1d8780ee80fb6a254644f5ed686064797b93c1f",
        "summary": "706ae0a26b379b3a91f1563f868c044dfdb30ec528ce83e71820f1917d28dcf5",
    },
    "ctc": {
        "step_matrix": "59bedf9c7a269812bf70d00816680bf550d21af821a3d97ffe5c765d33556abb",
        "operations": "7e3f7957abceeca0d62f4e9231cecd9ddd75c187a1fb0e383fba6f9e253bed45",
        "reagent_plan": "83c1764d7f4cc24b348af81bdd3494049788cce07bba4b94ed64d0ab5c0c88eb",
        "step_materials": "5f4c1ee9f3ca558f229d5559b2ec55aa09afafa4c4c53558301b130016079196",
        "materials": "c86b7fc3446c8942a114b4c175c5957188cb24835b90c6f33564682b463b1b65",
        "cleavage": "8b27bab9e320be6fc4a181be586d9ed8540d3f3a97df00d066f9ef3d6eb715cf",
        "validation": "89b0e3b1b718221d63c7f8021f41bd006401f4288e90da67fafcd964fb83911b",
        "summary": "82e9092704baab40be452e716c3e8209edded55ab47257cb8171b4f5b1d355ec",
    },
    "branch": {
        "step_matrix": "1af96ccc84291659af117de3b0865c555768f60ad8117e7edbe1780e0467d77c",
        "operations": "b67b2e6bc05d91ddd247c795c3a0069717117580740e698a3d997971ed9497ef",
        "reagent_plan": "64899d06a5f8cb393c21d7b627651dd7363032c922bac938de758ba163dd04dd",
        "step_materials": "f196542f760cc458fe00d1cd4136445b7dcb37ce569a4926fa203883dd2656ae",
        "materials": "cdefcbc6635129d5b94c18195f1195c5b8a46f3d48f07eb1b774b355749acf62",
        "cleavage": "0755c613adb63e7acd60a82c33d843a0f9eaf2996cc9286ee0c305e5ed8cb5c4",
        "validation": "fc7afc76fc6eec71461e9c1b19ecea65fe762806895e9e61e84c8d1b077497c8",
        "summary": "f9dce01d83b022eb2de1a087d85b7d085038bffd34f04872f1e4f18200d3be28",
    },
}


def test_accepted_engine_outputs_remain_byte_equivalent_after_normalization():
    actual = {
        scenario: {
            output: _digest(generator(plan))
            for output, generator in GENERATORS.items()
        }
        for scenario, plan in SCENARIOS.items()
    }
    assert actual == EXPECTED
