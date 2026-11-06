import pytest
from peptiforg_core.v6_physics_bridge import prepare_gaff_complex

@pytest.mark.parametrize('steps', [-1, 100001, 1.5, True, '50', None])
def test_bad_iteration_budget_fails_before_dependency_loading(steps):
    with pytest.raises(ValueError, match='minimize_steps'):
        prepare_gaff_complex('missing.pdb', 'missing.sdf', 'out', minimize_steps=steps)
