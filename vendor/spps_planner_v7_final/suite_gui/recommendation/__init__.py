"""Version-neutral canonical recommendation namespace.

Submodules are imported lazily so canonical owners do not depend on legacy
compatibility modules during package initialization.
"""
__all__ = ["loading", "cleavage", "coupling", "models", "model_registry", "provenance"]
