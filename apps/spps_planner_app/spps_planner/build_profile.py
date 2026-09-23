"""Build profile for SPPS Planner V5.0.0.

Only this small profile module and bundled data/policy files are allowed to differ
between Public and Private packages. Shared planner/recommendation code remains common.
"""
BUILD_FLAVOR = "PUBLIC"
IS_PRIVATE = BUILD_FLAVOR == "PRIVATE"
APP_FOLDER = "SPPS_Planner_PRIVATE" if IS_PRIVATE else "SPPS_Planner_PUBLIC"
FALLBACK_DOT_DIR = ".spps_planner_private" if IS_PRIVATE else ".spps_planner_public"
SESSION_FOLDER = "SPPS Planner Private" if IS_PRIVATE else "SPPS Planner Public"
BUNDLE_EXPERIMENTAL_SEEDS = IS_PRIVATE

__all__ = ["BUILD_FLAVOR", "IS_PRIVATE", "APP_FOLDER", "FALLBACK_DOT_DIR", "SESSION_FOLDER", "BUNDLE_EXPERIMENTAL_SEEDS"]
