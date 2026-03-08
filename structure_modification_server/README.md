# Structure Modification Server (MCP)

Accepts a CIF path or material identification from the first server’s JSON route (**results.json** / **results_short.json**). Builds a fairchem slab with the same doping/strain pathways as `optimade_adsorbml`, serializes it to a local `.pkl` file, and returns the file path.

- **main.py**: MCP server; calls **functions.py** via subprocess.
- **functions.py**: Loads structure from CIF or results.json, builds slab, applies doping/strain, pickles slab, returns path.

## Install and run

```bash
cd structure_modification_server
uv sync   # or: pip install -e .
python main.py
```

## Tool

- `create_and_serialize_slab(...)` → JSON with `serialized_slab_path`, `source`, `hkl`, `modifications_applied`.

Input: either `cif_path` or `results_json_path` + `provider` + `identifier` (from structure_retrieval server).
