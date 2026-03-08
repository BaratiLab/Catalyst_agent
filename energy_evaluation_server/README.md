# Energy Evaluation Server (MCP)

Runs AdsorbML energy evaluation. Accepts:

1. **Pymatgen structure** from the JSON route: **results_json_path** + **provider** + **identifier** (from structure_retrieval server).
2. **CIF file path**.
3. **Path to serialized slab** from the structure_modification server.

- **main.py**: MCP server; proxies to **functions.py** via subprocess for adsorbml runs.
- **functions.py**: Resolves slab (from file, CIF, or results.json), runs `run_adsorbml`, returns analysis summary and minimum energy results.

## Install and run

```bash
cd energy_evaluation_server
uv sync   # or: pip install -e .
python main.py
```

## Tool

- `adsorbml_evaluate(...)` → JSON with `source`, `analysis_summary`, `minimum_energy_results`.

Provide one of: `slab_path`, `cif_path`, or (`results_json_path`, `provider`, `identifier`).
