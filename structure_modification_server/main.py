"""
MCP server: structure modification. Accepts CIF path or (results_json_path + provider + identifier)
from the first server's JSON route; creates fairchem slab with same doping/strain pathways;
serializes slab to file and returns the file path.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("structure-modification")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("structure_modification_mcp")


def safe_json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def run_subprocess_function(function_name: str, payload: str) -> str:
    script_dir = Path(__file__).resolve().parent
    functions_path = script_dir / "functions.py"
    cmd = [sys.executable, str(functions_path), function_name, payload]
    logger.info(f"Running create_and_serialize_slab (payload keys: {list(json.loads(payload).keys())})")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(script_dir),
        timeout=300,
    )
    if result.returncode != 0:
        return safe_json_dumps({"error": result.stderr or f"returncode={result.returncode}"})
    return result.stdout.strip()


@mcp.tool()
async def create_and_serialize_slab(
    cif_path: Optional[str] = None,
    results_json_path: Optional[str] = None,
    provider: Optional[str] = None,
    identifier: Optional[str] = None,
    hkl: Optional[List[int]] = None,
    doping_target: Optional[str] = None,
    doping_new_symbol: Optional[str] = None,
    strain: Optional[float] = None,
    output_dir: str = "",
    slab_filename: Optional[str] = None,
) -> str:
    """
    Create a fairchem slab from a CIF file or from material identification in the first server's
    JSON route (results.json / results_short.json). Optionally apply doping and in-plane strain
    (same pathways as optimade_adsorbml). Serialize the slab to a local file and return its path.

    Provide either:
      - cif_path: path to a CIF file, or
      - results_json_path + provider + identifier: path to results.json and material id from the
        structure_retrieval server (e.g. from results_short.json).

    Args:
        cif_path: Path to CIF file (optional if results_json_path + provider + identifier given).
        results_json_path: Path to results.json produced by structure_retrieval server.
        provider: Provider key (e.g. "mp") from results_short.json.
        identifier: Identifier (e.g. "mp-1435808") from results_short.json.
        hkl: Miller indices [h, k, l] for slab (default [0, 0, 1]).
        doping_target: Element symbol to replace on the top surface.
        doping_new_symbol: Element symbol to substitute.
        strain: In-plane strain (positive = compressive, e.g. 0.03 for 3%).
        output_dir: Directory to write the serialized slab .pkl file (default: server cwd).
        slab_filename: Optional filename for the .pkl file (default: auto-generated).

    Returns:
        JSON with serialized_slab_path, source, hkl, modifications_applied.
    """
    if not cif_path and not (results_json_path and provider and identifier):
        return safe_json_dumps({
            "error": "Provide either cif_path or (results_json_path, provider, identifier)",
        })
    payload = {
        "cif_path": cif_path,
        "results_json_path": results_json_path,
        "provider": provider,
        "identifier": identifier,
        "hkl": hkl or [0, 0, 1],
        "doping_target": doping_target,
        "doping_new_symbol": doping_new_symbol,
        "strain": strain,
        "output_dir": output_dir or os.getcwd(),
        "slab_filename": slab_filename,
    }
    return run_subprocess_function("create_and_serialize_slab", json.dumps(payload))


if __name__ == "__main__":
    print("Starting structure modification MCP server...")
    logger.info("Starting structure modification MCP server...")
    mcp.run(transport="stdio")
