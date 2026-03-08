#!/usr/bin/env python3
"""
AdsorbML energy evaluation. Accepts:
  - serialized slab path (from structure_modification_server), or
  - CIF path, or
  - results.json path + provider + identifier (material from structure_retrieval_server).
Builds slab when needed (CIF or results), then runs adsorbml via run_adsorbml.
Called via subprocess from the MCP server.
"""

import json
import logging
import os
import pickle
import sys
from typing import Any, Dict, List, Optional, Tuple

# Use local fairchem installation (Catalyst_agent/fairchem) so it takes precedence over installed package.
fairchem_src_path = "/home/achuthchandrasekhar/Catalyst_agent/fairchem/src"
if fairchem_src_path in sys.path:
    sys.path.remove(fairchem_src_path)
sys.path.insert(0, fairchem_src_path)

import numpy as np
from ase import Atoms
from ase.io import read as ase_read
from ase.optimize import LBFGS

from fairchem.core.calculate.pretrained_mlip import get_predict_unit
from fairchem.core.calculate.ase_calculator import FAIRChemCalculator
from fairchem.data.oc.core.bulk import Bulk
from fairchem.data.oc.core.slab import Slab, compute_slabs, tile_and_tag_atoms
from fairchem.core.components.calculate.recipes.adsorbml import run_adsorbml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("energy_evaluation_functions")


def safe_json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def get_calc(model_name: str = "uma-s-1p1", device: str = "cuda"):
    predictor = get_predict_unit(model_name, device=device)
    return FAIRChemCalculator(predictor, task_name="oc20")


def load_slab_from_pickle(slab_path: str) -> Slab:
    if not os.path.exists(slab_path):
        raise FileNotFoundError(f"slab_path not found: {slab_path}")
    with open(slab_path, "rb") as f:
        return pickle.load(f)


def load_atoms_from_cif(cif_path: str) -> Atoms:
    if not os.path.exists(cif_path):
        raise FileNotFoundError(f"cif_path not found: {cif_path}")
    return ase_read(cif_path)


def load_atoms_from_results(results_json_path: str, provider: str, identifier: str) -> Atoms:
    if not os.path.exists(results_json_path):
        raise FileNotFoundError(f"results.json not found: {results_json_path}")
    with open(results_json_path, "r") as f:
        results = json.load(f)
    if provider not in results or identifier not in results[provider]:
        raise KeyError(f"Provider '{provider}' or identifier '{identifier}' not in results")
    d = results[provider][identifier]
    return Atoms(
        symbols=d["symbols"],
        positions=np.array(d["positions"]),
        cell=np.array(d["cell"]),
        pbc=d["pbc"],
    )


def build_slab(atoms: Atoms, hkl: Tuple[int, int, int]) -> Slab:
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


def adsorbml_evaluate_impl(
    slab_path: Optional[str] = None,
    cif_path: Optional[str] = None,
    results_json_path: Optional[str] = None,
    provider: Optional[str] = None,
    identifier: Optional[str] = None,
    hkl: Tuple[int, int, int] = (0, 0, 1),
    adsorbate: str = "*OH",
    device: str = "cuda",
) -> str:
    """
    Resolve slab from slab_path, cif_path, or (results_json_path, provider, identifier).
    Run adsorbml and return JSON with analysis_summary and minimum_energy_results.
    """
    if slab_path:
        slab = load_slab_from_pickle(slab_path)
        source = {"type": "serialized_slab", "path": slab_path}
        structure_data = {"formula": slab.atoms.get_chemical_formula(empirical=True), "spacegroup": None}
        provider_out = None
        identifier_out = None
    elif cif_path:
        atoms = load_atoms_from_cif(cif_path)
        slab = build_slab(atoms, hkl)
        source = {"type": "cif", "path": cif_path}
        structure_data = {"formula": atoms.get_chemical_formula(empirical=True), "spacegroup": None}
        provider_out = None
        identifier_out = None
    elif results_json_path and provider and identifier:
        atoms = load_atoms_from_results(results_json_path, provider, identifier)
        slab = build_slab(atoms, hkl)
        with open(results_json_path, "r") as f:
            res = json.load(f)
        structure_data = res[provider][identifier]
        structure_data = {"formula": structure_data.get("formula"), "spacegroup": structure_data.get("spacegroup")}
        source = {"type": "results_json", "path": results_json_path, "provider": provider, "identifier": identifier}
        provider_out = provider
        identifier_out = identifier
    else:
        return safe_json_dumps({
            "error": "Provide one of: slab_path, cif_path, or (results_json_path, provider, identifier)",
        })

    calc = get_calc(model_name="uma-s-1p1", device=device)
    logger.info("Running adsorbml analysis")
    results_adsorbml = run_adsorbml(
        slab=slab,
        adsorbate=adsorbate,
        calculator=calc,
        optimizer_cls=LBFGS,
        fmax=0.05,
        steps=300,
        num_placements=30,
        reference_ml_energies=True,
        place_on_relaxed_slab=True,
    )

    n_inits = len(results_adsorbml.get("adslab_anomalies", []))
    n_valid = len(results_adsorbml.get("adslabs", []))
    min_energy_config = None
    if n_valid > 0:
        for i, config in enumerate(results_adsorbml["adslabs"]):
            ref_energy_data = (config.get("results") or {}).get("referenced_adsorption_energy", {})
            if ref_energy_data and "adsorption_energy" in ref_energy_data:
                ae = float(ref_energy_data["adsorption_energy"])
                if min_energy_config is None or ae < min_energy_config.get("adsorption_energy", float("inf")):
                    min_energy_config = {
                        "config_index": i,
                        "adsorption_energy": ae,
                        "slab_energy": float(ref_energy_data.get("slab_energy", 0)),
                        "gas_reactant_energy": float(ref_energy_data.get("gas_reactant_energy", 0)),
                        "adslab_energy": float(ref_energy_data.get("adslab_energy", 0)),
                    }
    response: Dict[str, Any] = {
        "source": source,
        "provider": provider_out,
        "identifier": identifier_out,
        "formula": structure_data.get("formula"),
        "spacegroup": structure_data.get("spacegroup"),
        "adsorbate": adsorbate,
        "hkl": list(hkl),
        "cif_path": cif_path,
        "slab_path": slab_path,
        "analysis_summary": {
            "total_configurations": n_inits,
            "valid_configurations": n_valid,
            "anomalies_detected": sum(len(a) for a in results_adsorbml.get("adslab_anomalies", [])),
        },
    }
    if min_energy_config:
        response["minimum_energy_results"] = min_energy_config
    else:
        response["error"] = "No valid configurations found for adsorbml analysis"
    return safe_json_dumps(response)


def main():
    if len(sys.argv) < 2:
        print(safe_json_dumps({"error": "No function specified"}))
        return
    function_name = sys.argv[1]
    if function_name != "adsorbml_evaluate":
        print(safe_json_dumps({"error": f"Unknown function: {function_name}"}))
        return
    if len(sys.argv) < 3:
        print(safe_json_dumps({"error": "Missing JSON payload"}))
        return
    try:
        params = json.loads(sys.argv[2])
    except json.JSONDecodeError as e:
        print(safe_json_dumps({"error": f"Invalid JSON: {e}"}))
        return

    slab_path = params.get("slab_path") or None
    cif_path = params.get("cif_path") or None
    results_json_path = params.get("results_json_path") or None
    provider = params.get("provider") or None
    identifier = params.get("identifier") or None
    hkl_list = params.get("hkl", [0, 0, 1])
    hkl = (int(hkl_list[0]), int(hkl_list[1]), int(hkl_list[2]))
    adsorbate = params.get("adsorbate") or "*OH"
    device = params.get("device") or "cuda"

    try:
        result = adsorbml_evaluate_impl(
            slab_path=slab_path,
            cif_path=cif_path,
            results_json_path=results_json_path,
            provider=provider,
            identifier=identifier,
            hkl=hkl,
            adsorbate=adsorbate,
            device=device,
        )
        print(result)
    except Exception as e:
        logger.exception("adsorbml_evaluate failed")
        print(safe_json_dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
