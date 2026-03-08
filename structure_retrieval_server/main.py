"""
MCP server: structure retrieval (OPTIMADE structure search only).
Writes results.json and results_short.json; returns paths as link to pymatgen structures.
main.py acts as proxy to functions.py via subprocess.
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import List

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("structure-retrieval")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("structure_retrieval_mcp")


def safe_json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def run_subprocess_function(function_name: str, *args) -> str:
    script_dir = Path(__file__).resolve().parent
    functions_path = script_dir / "functions.py"
    cmd = [sys.executable, str(functions_path), function_name] + [str(a) for a in args]
    logger.info(f"Running: {' '.join(cmd)}")
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
async def optimade_structure_search(
    elements: List[str],
    nelements: int,
    output_dir: str = "",
) -> str:
    """
    Search for structures using OPTIMADE. Writes results.json and results_short.json
    (same JSON route as optimade_adsorbml) and returns the paths (link to pymatgen structures).

    Args:
        elements: List of element symbols to search for.
        nelements: Number of elements in the structures.
        output_dir: Directory to write results.json and results_short.json (default: server cwd).

    Returns:
        JSON with results_json_path, results_short_json_path, results_summary, files_saved.
    """
    out = output_dir or os.getcwd()
    return run_subprocess_function("optimade_structure_search", ",".join(elements), nelements, out)


if __name__ == "__main__":
    print("Starting structure retrieval MCP server...")
    logger.info("Starting structure retrieval MCP server...")
    mcp.run(transport="stdio")
