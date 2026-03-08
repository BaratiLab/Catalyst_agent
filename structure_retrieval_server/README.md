# Structure Retrieval Server (MCP)

Runs OPTIMADE structure search and writes **results.json** and **results_short.json** (same JSON route as `optimade_adsorbml`). Returns paths to these files as the link to pymatgen structures.

- **main.py**: MCP server; proxies to **functions.py** via subprocess.
- **functions.py**: Implements `optimade_structure_search`; writes results to `output_dir`.

## Install and run

```bash
cd structure_retrieval_server
uv sync   # or: pip install -e .
python main.py
```

## Tool

- `optimade_structure_search(elements, nelements, output_dir?)` → JSON with `results_json_path`, `results_short_json_path`, `results_summary`.
