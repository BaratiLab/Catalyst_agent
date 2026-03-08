#!/usr/bin/env python3
"""
Build fairchem slab from CIF or from results.json (material identification);
apply doping and strain same as optimade_adsorbml; serialize slab to file; return path.
Called via subprocess from the MCP server.
"""

import json
import logging
import os
import pickle
import sys
from typing import List, Optional, Tuple

import numpy as np
from ase import Atoms
from ase.io import read as ase_read

# Use local fairchem installation (Catalyst_agent/fairchem) so it takes precedence over installed package.
fairchem_src_path = "/home/achuthchandrasekhar/Catalyst_agent/fairchem/src"
if fairchem_src_path in sys.path:
    sys.path.remove(fairchem_src_path)
sys.path.insert(0, fairchem_src_path)

from fairchem.data.oc.core.bulk import Bulk
from fairchem.data.oc.core.slab import Slab, compute_slabs, tile_and_tag_atoms

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("structure_modification_functions")


def safe_json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def load_atoms_from_cif(cif_path: str) -> Atoms:
    if not os.path.exists(cif_path):
        raise FileNotFoundError(f"cif_path not found: {cif_path}")
    return ase_read(cif_path)


def load_atoms_from_results(results_json_path: str, provider: str, identifier: str) -> Atoms:
    if not os.path.exists(results_json_path):
        raise FileNotFoundError(f"results.json not found: {results_json_path}")
    with open(results_json_path, "r") as f:
        results = json.load(f)
    if provider not in results:
        raise KeyError(f"Provider '{provider}' not found in results")
    if identifier not in results[provider]:
        raise KeyError(f"Identifier '{identifier}' not found for provider '{provider}'")
    structure_data = results[provider][identifier]
    return Atoms(
        symbols=structure_data["symbols"],
        positions=np.array(structure_data["positions"]),
        cell=np.array(structure_data["cell"]),
        pbc=structure_data["pbc"],
    )


def build_slab_impl(
    hkl: Tuple[int, int, int],
    atoms: Atoms,
) -> Slab:
    bulk = Bulk(atoms)
    specific_millers = tuple(int(v) for v in hkl)
    max_miller = max(abs(v) for v in specific_millers)
    min_ab = 8.0 if max_miller <= 3 else 6.0

    untiled_slabs = compute_slabs(
        bulk.atoms,
        max_miller=max_miller,
        specific_millers=[specific_millers],
    )
    if not untiled_slabs:
        raise ValueError("Could not create slab from structure")

    slab_struct, millers, shift, top, oriented_bulk = untiled_slabs[0]
    slab_atoms_tiled = tile_and_tag_atoms(slab_struct, bulk.atoms, min_ab=min_ab)
    return Slab(
        bulk=bulk,
        slab_atoms=slab_atoms_tiled,
        millers=millers,
        shift=shift,
        top=top,
        oriented_bulk=oriented_bulk,
        min_ab=min_ab,
    )


def apply_doping(slab: Slab, doping_target: str, doping_new_symbol: str) -> dict:
    modifications = {}
    slab_atoms = slab.atoms.copy()
    scaled = slab_atoms.get_scaled_positions(wrap=True)
    zfrac = scaled[:, 2]
    zmax = zfrac.max()
    frac_tol = 0.03
    top_candidates = np.where(zfrac >= zmax - frac_tol)[0]
    top_targets = [i for i in top_candidates if slab_atoms[i].symbol == doping_target]
    if not top_targets:
        top_targets = [i for i, a in enumerate(slab_atoms) if a.symbol == doping_target]
    if top_targets:
        cart_z = slab_atoms.get_positions()[:, 2]
        top_i = max(top_targets, key=lambda i: cart_z[i])
        old_symbol = slab_atoms[top_i].symbol
        slab_atoms[top_i].symbol = doping_new_symbol
        slab.atoms = slab_atoms
        modifications["doping"] = {
            "target": doping_target,
            "new_symbol": doping_new_symbol,
            "atom_index": int(top_i),
            "original_symbol": old_symbol,
        }
    else:
        modifications["doping"] = {"error": f"No atoms of element '{doping_target}' found"}
    return modifications


def apply_strain(slab: Slab, strain: float) -> dict:
    cell = slab.atoms.get_cell().array.copy()
    cell[0] *= (1.0 - strain)
    cell[1] *= (1.0 - strain)
    slab.atoms.set_cell(cell, scale_atoms=True)
    return {
        "strain": {
            "value": strain,
            "percentage": abs(strain) * 100,
            "type": "compressive" if strain > 0 else "tensile",
        }
    }


def create_and_serialize_slab_impl(
    cif_path: Optional[str] = None,
    results_json_path: Optional[str] = None,
    provider: Optional[str] = None,
    identifier: Optional[str] = None,
    hkl: Tuple[int, int, int] = (0, 0, 1),
    doping_target: Optional[str] = None,
    doping_new_symbol: Optional[str] = None,
    strain: Optional[float] = None,
    output_dir: str = ".",
    slab_filename: Optional[str] = None,
) -> str:
    """
    Load structure from CIF or results.json; build fairchem slab; apply doping/strain;
    serialize slab to a .pkl file; return JSON with serialized_slab_path and metadata.
    """
    if cif_path:
        atoms = load_atoms_from_cif(cif_path)
        source = {"type": "cif", "path": cif_path}
    elif results_json_path and provider and identifier:
        atoms = load_atoms_from_results(results_json_path, provider, identifier)
        source = {"type": "results_json", "path": results_json_path, "provider": provider, "identifier": identifier}
    else:
        return safe_json_dumps({
            "error": "Provide either cif_path or (results_json_path, provider, identifier)",
        })

    slab = build_slab_impl(hkl, atoms)
    modifications_applied = {}

    if doping_target and doping_new_symbol:
        mod = apply_doping(slab, doping_target, doping_new_symbol)
        modifications_applied.update(mod)

    if strain is not None and strain != 0:
        mod = apply_strain(slab, strain)
        modifications_applied.update(mod)

    os.makedirs(output_dir, exist_ok=True)
    if not slab_filename:
        id_part = f"{provider}_{identifier}" if (provider and identifier) else os.path.splitext(os.path.basename(cif_path or ""))[0] or "cif"
        base = f"slab_{id_part}_{hkl[0]}{hkl[1]}{hkl[2]}"
        slab_filename = f"{base}.pkl"
    out_path = os.path.join(output_dir, slab_filename)
    with open(out_path, "wb") as f:
        pickle.dump(slab, f)

    abs_path = os.path.abspath(out_path)
    logger.info(f"Serialized slab to {abs_path}")

    return safe_json_dumps({
        "serialized_slab_path": abs_path,
        "source": source,
        "hkl": list(hkl),
        "modifications_applied": modifications_applied or None,
        "message": f"Slab created and saved to {abs_path}",
    })


def main():
    if len(sys.argv) < 2:
        print(safe_json_dumps({"error": "No function specified"}))
        return

    function_name = sys.argv[1]
    if function_name != "create_and_serialize_slab":
        print(safe_json_dumps({"error": f"Unknown function: {function_name}"}))
        return

    # Parse: cif_path or results_json_path, provider, identifier, hkl, doping_target, doping_new_symbol, strain, output_dir, slab_filename
    # We pass a single JSON blob as arg 2 to avoid quoting issues
    if len(sys.argv) < 3:
        print(safe_json_dumps({"error": "Missing JSON argument"}))
        return

    try:
        params = json.loads(sys.argv[2])
    except json.JSONDecodeError as e:
        print(safe_json_dumps({"error": f"Invalid JSON: {e}"}))
        return

    cif_path = params.get("cif_path") or None
    results_json_path = params.get("results_json_path") or None
    provider = params.get("provider") or None
    identifier = params.get("identifier") or None
    hkl_list = params.get("hkl", [0, 0, 1])
    hkl = (int(hkl_list[0]), int(hkl_list[1]), int(hkl_list[2]))
    doping_target = params.get("doping_target") or None
    doping_new_symbol = params.get("doping_new_symbol") or None
    strain = params.get("strain")
    if strain is not None:
        strain = float(strain)
    output_dir = params.get("output_dir", ".")
    slab_filename = params.get("slab_filename") or None

    try:
        result = create_and_serialize_slab_impl(
            cif_path=cif_path,
            results_json_path=results_json_path,
            provider=provider,
            identifier=identifier,
            hkl=hkl,
            doping_target=doping_target,
            doping_new_symbol=doping_new_symbol,
            strain=strain,
            output_dir=output_dir,
            slab_filename=slab_filename,
        )
        print(result)
    except Exception as e:
        logger.exception("create_and_serialize_slab failed")
        print(safe_json_dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
