#!/usr/bin/env python3
"""
OPTIMADE structure search implementation. Writes results.json and results_short.json
to the given output directory (or cwd). Called via subprocess from the MCP server.
"""

import json
import logging
import os
import sys
from typing import List

import pandas as pd
from pymatgen.ext.optimade import OptimadeRester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("structure_retrieval_functions")


def safe_json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def optimade_structure_search_impl(
    elements: List[str],
    nelements: int,
    output_dir: str = ".",
) -> str:
    """
    Run OPTIMADE structure search and write results.json and results_short.json
    to output_dir. Returns JSON with paths and summary (link to pymatgen structures).
    """
    try:
        opt = OptimadeRester(["mp", "oqmd"], timeout=20)
        logger.info(f"Searching for structures with elements {elements} and nelements={nelements}")
        results = opt.get_structures(elements=elements, nelements=nelements)

        os.makedirs(output_dir, exist_ok=True)
        results_path = os.path.join(output_dir, "results.json")
        results_short_path = os.path.join(output_dir, "results_short.json")

        with open(results_path, "w") as f:
            serializable_results = {}
            for provider, structures in results.items():
                serializable_results[provider] = {}
                for identifier, structure in structures.items():
                    # Avoid requiring ASE at runtime; export directly from pymatgen Structure.
                    symbols = [
                        sp.symbol if hasattr(sp, "symbol") else str(sp)
                        for sp in structure.species
                    ]
                    serializable_results[provider][identifier] = {
                        "formula": structure.composition.reduced_formula,
                        "spacegroup": structure.get_space_group_info()[0],
                        "lattice_params": {
                            "a": structure.lattice.a,
                            "b": structure.lattice.b,
                            "c": structure.lattice.c,
                            "alpha": structure.lattice.alpha,
                            "beta": structure.lattice.beta,
                            "gamma": structure.lattice.gamma,
                        },
                        "volume": structure.volume,
                        "positions": structure.cart_coords.tolist(),
                        "symbols": symbols,
                        "cell": structure.lattice.matrix.tolist(),
                        "pbc": [True, True, True],
                    }
            json.dump(serializable_results, f, indent=2)

        records = []
        for provider, structures in results.items():
            for identifier, structure in structures.items():
                records.append({
                    "provider": provider,
                    "identifier": identifier,
                    "formula": structure.composition.reduced_formula,
                    "spacegroup": structure.get_space_group_info()[0],
                })

        df = pd.DataFrame(records)
        df.to_json(results_short_path, orient="records", indent=2)

        logger.info(f"Saved results to {results_path} and {results_short_path}")

        return safe_json_dumps({
            "message": f"Found {len(records)} structures matching criteria",
            "results_json_path": os.path.abspath(results_path),
            "results_short_json_path": os.path.abspath(results_short_path),
            "results_summary": records,
            "files_saved": ["results.json", "results_short.json"],
        })
    except Exception as e:
        logger.error(f"OPTIMADE search error: {e}")
        return safe_json_dumps({"error": str(e)})


def main():
    if len(sys.argv) < 2:
        print(safe_json_dumps({"error": "No function specified"}))
        return

    function_name = sys.argv[1]
    if function_name != "optimade_structure_search":
        print(safe_json_dumps({"error": f"Unknown function: {function_name}"}))
        return

    if len(sys.argv) < 4:
        print(safe_json_dumps({"error": "Missing arguments: elements and nelements required"}))
        return

    elements = sys.argv[2].split(",")
    nelements = int(sys.argv[3])
    output_dir = sys.argv[4] if len(sys.argv) > 4 else "."

    result = optimade_structure_search_impl(elements, nelements, output_dir)
    print(result)


if __name__ == "__main__":
    main()
