#!/usr/bin/env python3
"""
ECHA Chemical Data CLI — query European Chemicals Agency data from the command line.

Usage:
    echa-cli search ethanol
    echa-cli search 50-00-0
    echa-cli substance-info 100.000.002
    echa-cli harmonised 100.000.002
    echa-cli tox-summary 100.000.002
"""

import asyncio
import json
import sys
from typing import Optional

import typer

app = typer.Typer(
    name="echa-cli",
    help="ECHA Chemical Data CLI — query European Chemicals Agency data.",
    no_args_is_help=True,
)


def _run_async(coro):
    """Run an async coro, print its JSON result, then clean up the httpx client."""
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(coro)
        typer.echo(result)
    except Exception as e:
        typer.echo(f'{{"error": "{e}"}}', err=True)
        raise typer.Exit(code=1)
    finally:
        from .clients.echa_client import get_client

        try:
            loop.run_until_complete(get_client().close())
        except Exception:
            pass
        loop.close()


# ─── Search (resolve CAS/name → substance_index) ─────────────


@app.command()
def search(
    query: str = typer.Argument(help="CAS number, chemical name, or EC number"),
    max_results: int = typer.Option(5, help="Maximum results to return"),
):
    """Search ECHA for a substance by CAS number, name, or EC number. Returns substance_index."""
    async def _search():
        from .clients.echa_client import get_client

        client = get_client()
        http_client = await client._get_client()

        url = "/api-substance/v1/substance"
        params = {"searchText": query, "pageIndex": 1, "pageSize": max_results}
        resp = await http_client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        if not items:
            return json.dumps({"error": f"No results for '{query}'"}, indent=2)

        results = []
        for item in items[:max_results]:
            idx = item.get("substanceIndex", {})
            results.append({
                "substance_index": idx.get("rmlId", ""),
                "name": idx.get("rmlName", ""),
                "cas_number": idx.get("rmlCas", ""),
                "ec_number": idx.get("rmlEc", ""),
                "molecular_formula": idx.get("rmlMolFormula", ""),
            })

        return json.dumps({"query": query, "total": len(results), "results": results}, ensure_ascii=False, indent=2)

    _run_async(_search())


# ─── Substance Info ───────────────────────────────────────────


@app.command()
def substance_info(substance_index: str):
    """Get substance basic info (CAS, EC, names, formula, SMILES)."""
    from .tools.substance import get_substance_info

    _run_async(get_substance_info(substance_index))


@app.command()
def list_dossiers(
    substance_index: str,
    status: str = typer.Option("Active", help="Registration status: 'Active' or 'Not active'"),
    max_results: int = typer.Option(10, help="Maximum dossiers to return"),
):
    """List REACH registration dossiers."""
    from .tools.substance import list_dossiers

    _run_async(list_dossiers(substance_index, status, max_results))


# ─── Classification ───────────────────────────────────────────


@app.command()
def clp(
    substance_index: str,
    max_results: int = typer.Option(5, help="Maximum classifications to return"),
):
    """Get CLP industry notification classification."""
    from .tools.clp_classification import get_clp_classification

    _run_async(get_clp_classification(substance_index, max_results))


@app.command()
def harmonised(substance_index: str):
    """Get harmonised classification (Annex VI, legally binding)."""
    from .tools.harmonised_classification import get_harmonised_classification

    _run_async(get_harmonised_classification(substance_index))


@app.command()
def reach_ghs(substance_index: str, cas_number: str):
    """Get REACH GHS classification from dossier Section 2.1."""
    from .tools.reach_classification import get_reach_ghs

    _run_async(get_reach_ghs(substance_index, cas_number))


@app.command()
def reach_pbt(substance_index: str, cas_number: str):
    """Get REACH PBT/vPvB assessment from dossier Section 2.3."""
    from .tools.reach_classification import get_reach_pbt

    _run_async(get_reach_pbt(substance_index, cas_number))


# ─── Toxicology ───────────────────────────────────────────────


@app.command()
def tox_summary(substance_index: str):
    """Get toxicology summary + DN(M)ELs (Section 7, fast ~10-30s)."""
    from .tools.toxicology import get_toxicology_summary

    _run_async(get_toxicology_summary(substance_index))


@app.command()
def tox_studies(
    substance_index: str,
    section: Optional[str] = typer.Option(None, help="Filter by subsection (e.g. 7.2)"),
    max_studies: int = typer.Option(50, help="Maximum studies to parse"),
):
    """Get individual toxicology study records (Section 7)."""
    from .tools.toxicology import get_toxicology_studies

    _run_async(get_toxicology_studies(substance_index, section, max_studies))


@app.command()
def tox_full(substance_index: str):
    """Get complete toxicology data (Section 7, slow up to ~5 min)."""
    from .tools.toxicology import get_toxicology_full

    _run_async(get_toxicology_full(substance_index))
