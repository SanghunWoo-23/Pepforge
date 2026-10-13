"""Stable cleavage recommendation surface owned by the canonical recommendation implementation."""
from .loading import cleavage_advice, cleavage_recommendation, _inject_empirical_condition
__all__=['cleavage_advice','cleavage_recommendation','_inject_empirical_condition']


def advise(*, db_path=None, **query):
    return cleavage_advice(db_path=db_path, **query)

def recommend(*, db_path=None, **query):
    return cleavage_recommendation(db_path=db_path, **query)
