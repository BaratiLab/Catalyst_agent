"""
MCP server: energy evaluation (AdsorbML). Accepts pymatgen structure from JSON route
(results.json + provider + identifier), CIF path, or path to serialized slab.
main.py acts as proxy to functions.py via subprocess for adsorbml runs.
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("energy-evaluation")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("energy_evaluation_mcp")


def safe_json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def run_subprocess_function(function_name: str, payload: str) -> str:
    script_dir = Path(__file__).resolve().parent
    functions_path = script_dir / "functions.py"
    cmd = [sys.executable, str(functions_path), function_name, payload]
    logger.info(f"Running adsorbml via subprocess (payload keys: {list(json.loads(payload).keys())})")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(script_dir),
        timeout=600,
    )
    if result.returncode != 0:
        return safe_json_dumps({"error": result.stderr or f"returncode={result.returncode}"})
    return result.stdout.strip()


@mcp.tool()
async def adsorbml_evaluate(
    slab_path: Optional[str] = None,
    cif_path: Optional[str] = None,
    results_json_path: Optional[str] = None,
    provider: Optional[str] = None,
    identifier: Optional[str] = None,
    hkl: Optional[List[int]] = None,
    adsorbate: str = "*OH",
    device: str = "cuda",
) -> str:
    """
    Run AdsorbML energy evaluation. Provide one of:
      - slab_path: path to serialized fairchem slab (e.g. from structure_modification server)
      - cif_path: path to CIF file (slab will be built with hkl)
      - results_json_path + provider + identifier: material from structure_retrieval server
        (results.json / results_short.json); slab will be built with hkl.

    Args:
        slab_path: Path to .pkl serialized slab from create_and_serialize_slab.
        cif_path: Path to CIF file.
        results_json_path: Path to results.json from optimade_structure_search.
        provider: Provider from results_short.json (e.g. "mp").
        identifier: Identifier from results_short.json (e.g. "mp-1435808").
        hkl: Miller indices [h, k, l] when building slab from CIF or results (default [0,0,1]).
        adsorbate: Adsorbate species (default "*OH").
        device: "cuda" or "cpu" for calculator.

    Returns:
        JSON with source, analysis_summary, minimum_energy_results (or error).
    """
    if not slab_path and not cif_path and not (results_json_path and provider and identifier):
        return safe_json_dumps({
            "error": "Provide one of: slab_path, cif_path, or (results_json_path, provider, identifier)",
        })
    payload = {
        "slab_path": slab_path,
        "cif_path": cif_path,
        "results_json_path": results_json_path,
        "provider": provider,
        "identifier": identifier,
        "hkl": hkl or [0, 0, 1],
        "adsorbate": adsorbate,
        "device": device,
    }
    return run_subprocess_function("adsorbml_evaluate", json.dumps(payload))


if __name__ == "__main__":
    print("Starting energy evaluation MCP server...")
    logger.info("Starting energy evaluation MCP server...")
    mcp.run(transport="stdio")
