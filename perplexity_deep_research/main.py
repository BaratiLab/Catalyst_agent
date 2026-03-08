"""
MCP server for Perplexity Deep Research (Sonar).
Exposes a single tool: deep_research(query) -> response text.
"""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load .env from this package directory
_load_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_load_path)

# Initialize MCP after env is loaded (Perplexity client reads PERPLEXITY_API_KEY)
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("perplexity-deep-research")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("perplexity_deep_research_mcp")


def _get_client():
    """Lazy-import and create Perplexity client (requires API key from env)."""
    from perplexity import Perplexity
    return Perplexity()


@mcp.tool()
async def deep_research(query: str) -> str:
    """
    Run Perplexity Sonar Deep Research on a text query and return the full response.

    Uses the sonar-deep-research model to perform exhaustive research across
    many sources. Suitable for academic research, market analysis, and long-form reports.

    Args:
        query: The research question or topic (e.g. "find me 20 papers with polymer OPV data and return doi links").

    Returns:
        The model's response text. On failure, returns an error message string.
    """
    if not (query and query.strip()):
        return "Error: query must be a non-empty string."

    try:
        client = _get_client()
        completion = client.chat.completions.create(
            model="sonar-deep-research",
            messages=[{"role": "user", "content": query.strip()}],
        )
        content = completion.choices[0].message.content
        return content if content else "(No content in response)"
    except Exception as e:
        msg = f"Perplexity deep research failed: {e}"
        logger.exception(msg)
        return msg


if __name__ == "__main__":
    try:
        print("Starting Perplexity Deep Research MCP server...")
        logger.info("Starting Perplexity Deep Research MCP server...")
        mcp.run(transport="stdio")
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()
