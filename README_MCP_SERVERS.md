# MCP Servers (5) — Setup + Run (uv)

This repo contains five MCP servers (stdio transport) used for structure retrieval, structure modification, energy evaluation, CIF file listing, and Perplexity deep research.

Servers included (excluding `optimade_adsorbml`):
- `cif_file_resource_server`
- `structure_retrieval_server`
- `structure_modification_server`
- `energy_evaluation_server`
- `perplexity_deep_research`

## Prerequisites

- Python 3.10+
- `uv` installed

Each server directory has its own `pyproject.toml`/`uv.lock`. Install deps per-server.

## Install dependencies (per server)

Run this once per server:

```bash
cd <server_dir>
uv sync
```

Examples:

```bash
cd cif_file_resource_server && uv sync
cd structure_retrieval_server && uv sync
cd structure_modification_server && uv sync
cd energy_evaluation_server && uv sync
cd perplexity_deep_research && uv sync
```

## Run a server (stdio)

Each server is an MCP stdio process:

```bash
cd <server_dir>
uv run python main.py
```

## Servers

### 1) `cif_file_resource_server`

Purpose: list CIFs under `cif_file_resource_server/cifs/` and return formula + space group.

Run:
```bash
cd cif_file_resource_server
uv sync
uv run python main.py
```

Tool exposed:
- `list_cif_files() -> str` (JSON array)

Notes:
- Requires `spglib` (used by ASE symmetry checks).

### 2) `structure_retrieval_server`

Purpose: query OPTIMADE (Materials Project + OQMD) and write `results.json` / `results_short.json`.

Run:
```bash
cd structure_retrieval_server
uv sync
uv run python main.py
```

Tool exposed:
- `optimade_structure_search(elements: List[str], nelements: int, output_dir: str="") -> str`

Outputs:
- `results.json`: full structure payloads (cell + cartesian coords + symbols)
- `results_short.json`: compact summary list (provider/id/formula/spacegroup)

### 3) `structure_modification_server`

Purpose: build a FairChem slab from a CIF or from `results.json`, optionally apply:
- surface doping (topmost atom replacement)
- in-plane strain (scales a/b lattice vectors)

Run:
```bash
cd structure_modification_server
uv sync
uv run python main.py
```

Tool exposed:
- `create_and_serialize_slab(...) -> str`

Outputs:
- a serialized slab pickle (`.pkl`) in `output_dir`

Notes:
- Some transitive deps import `pkg_resources`; the project pins `setuptools<81` to keep that import available.

### 4) `energy_evaluation_server`

Purpose: run AdsorbML to evaluate adsorption configurations on a slab, returning a minimum adsorption energy summary.

Run:
```bash
cd energy_evaluation_server
uv sync
uv run python main.py
```

Tool exposed:
- `adsorbml_evaluate(..., adsorbate="*OH", device="cuda") -> str`

Notes:
- `device="cuda"` requires a working NVIDIA GPU runtime (CUDA-visible device). Use `device="cpu"` if no GPU is available.
- Some transitive deps import `pkg_resources`; the project pins `setuptools<81` to keep that import available.

### 5) `perplexity_deep_research`

Purpose: call Perplexity “sonar-deep-research” and return the full response text.

Run:
```bash
cd perplexity_deep_research
uv sync
uv run python main.py
```

Tool exposed:
- `deep_research(query: str) -> str`

Environment:
- Set `PERPLEXITY_API_KEY` (this server loads `perplexity_deep_research/.env` if present).

## Example: MCP client command

Most MCP clients need a command to spawn the server. Typical command patterns are:

```bash
uv --directory <server_dir> run python main.py
```

or

```bash
cd <server_dir> && uv run python main.py
```

