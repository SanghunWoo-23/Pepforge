"""Identify *available* compute platforms; availability never implies an engine uses GPU."""
from __future__ import annotations

def inspect_compute_devices():
    result = {"native_docking": "CPU (native NumPy engine)", "openmm": {"installed": False, "platforms": [], "preferred": "unavailable"}, "torch": {"installed": False, "cuda_available": False, "device": "CPU"}}
    try:
        import openmm
        n = openmm.Platform.getNumPlatforms()
        platforms = [openmm.Platform.getPlatform(i).getName() for i in range(n)]
        preferred = next((v for v in ("CUDA", "OpenCL") if v in platforms), "CPU" if "CPU" in platforms else "Reference")
        result["openmm"] = {"installed": True, "platforms": platforms, "preferred": preferred}
    except (ImportError, OSError, RuntimeError) as exc:
        result["openmm"]["reason"] = str(exc)
    try:
        import torch
        available = bool(torch.cuda.is_available())
        result["torch"] = {"installed": True, "cuda_available": available, "device": torch.cuda.get_device_name(0) if available else "CPU"}
    except (ImportError, OSError, RuntimeError, AssertionError) as exc:
        result["torch"]["reason"] = str(exc)
    return result
