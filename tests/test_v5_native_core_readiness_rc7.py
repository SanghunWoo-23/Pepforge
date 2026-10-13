from pathlib import Path
from peptiforg_core.native_core_readiness_v1 import assess_native_core_readiness

def test_native_core_readiness_self_smoke(tmp_path):
    x=assess_native_core_readiness(tmp_path,run_self_smoke=True)
    assert x["overall_status"]=="NATIVE_CORE_SOFTWARE_READY_RESEARCH_VALIDATION_PENDING"
    assert x["self_smoke"]["status"]=="PASS"
    assert x["self_smoke"]["network_policy"]=="NO_NETWORK_CALLS_IN_NATIVE_E2E_MODULE"
    assert Path(tmp_path/"NATIVE_CORE_READINESS.json").exists()
