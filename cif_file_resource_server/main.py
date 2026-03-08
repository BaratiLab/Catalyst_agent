"""
MCP server that lists CIF files in the local cifs directory with formula and space group.
"""
import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cif_file_resource_server")

# Base directory of this package; cifs live in ./cifs
SERVER_DIR = Path(__file__).resolve().parent
CIFS_DIR = SERVER_DIR / "cifs"

mcp = FastMCP("cif-file-resource-server")


def _safe_json_dumps(obj):
    """Produce valid, double-quoted JSON."""
    return json.dumps(obj, ensure_ascii=False, indent=2)


def _get_cif_info(cif_path: Path) -> dict | None:
    """
    Read a CIF with ASE, compute formula and space group.
    Returns a dict for one file or None on failure.
    """
    try:
        import ase.io
        from ase.spacegroup.symmetrize import check_symmetry

        atoms = ase.io.read(str(cif_path))
        formula = atoms.get_chemical_formula(mode="reduce")
        sym = check_symmetry(atoms, symprec=1e-5)
        return {
            "path": str(cif_path),
            "formula": formula,
            "space_group_number": sym.number,
            "space_group_symbol": sym.international,
        }
    except Exception as e:
        logger.warning("Failed to read %s: %s", cif_path, e)
        return {
            "path": str(cif_path),
            "formula": None,
            "space_group_number": None,
            "space_group_symbol": None,
            "error": str(e),
        }


@mcp.tool()
async def list_cif_files() -> str:
    """
    List all CIF files in the server's cifs directory with their chemical formula
    and space group (number and international symbol).

    Returns:
        str: JSON array of objects, each with keys: path, formula, space_group_number, space_group_symbol.
             Failed files may include an "error" key; formula and space_group_* may be null.
    """
    if not CIFS_DIR.is_dir():
        return _safe_json_dumps([])

    results = []
    for path in sorted(CIFS_DIR.glob("*.cif")):
        info = _get_cif_info(path)
        if info:
            results.append(info)

    return _safe_json_dumps(results)


if __name__ == "__main__":
    try:
        print("Starting CIF file resource MCP server...")
        logger.info("Starting CIF file resource MCP server...")
        mcp.run(transport="stdio")
    except Exception as e:
        print(f"Error starting server: {e}")
        raise
