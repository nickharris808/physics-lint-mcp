"""physics-lint-mcp: physics validation as tools an AI agent can call.

Why this exists
---------------
Agents are increasingly asked to produce or evaluate RF and packaging models,
and an LLM has no way to tell a physically impossible S-parameter matrix from a
plausible one -- both are just numbers. Given a fabricated model an agent will
reason confidently about it, and nothing in the loop objects.

These tools give the agent a ground-truth oracle it cannot talk its way past.
The verdicts come from linear algebra, not from the model's judgement.

Design note: every tool is READ-ONLY and side-effect free. Nothing here writes,
fabricates or repairs a model -- an agent that could silently "fix" a failing
network would defeat the purpose.

Transport is JSON-RPC 2.0 over stdio, per the Model Context Protocol.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from . import __version__

PROTOCOL_VERSION = "2024-11-05"


# --------------------------------------------------------------------- tools

def _load_network(path: str):
    from sparam_lint import read_touchstone
    return read_touchstone(path)


def tool_check_touchstone(path: str) -> dict:
    """Check an S-parameter file against the five physical laws."""
    from sparam_lint import run_battery
    net = _load_network(path)
    results = run_battery(net.s, net.freq_hz, net.z0)
    failed = [r.name for r in results if not r.passed]
    return {
        "file": path,
        "n_ports": net.n_ports,
        "n_freq": net.n_freq,
        "z0_ohm": net.z0,
        "physically_admissible": not failed,
        "failed_laws": failed,
        "laws": [r.as_dict() for r in results],
        "interpretation": (
            "All five laws hold; the network is physically admissible. Note "
            "this does NOT mean it is accurate -- a passive model of the wrong "
            "structure passes every law here."
            if not failed else
            "This network is not physically realizable as a passive device. "
            "Do not use it as a reference and do not reason from its values. "
            "One legitimate exception: a non-reciprocal device such as a "
            "ferrite isolator will correctly fail the reciprocity law by "
            "design."
        ),
    }


def tool_self_test() -> dict:
    """Verify the checker still discriminates, via its negative control."""
    from sparam_lint import run_negative_control
    report = run_negative_control()
    return {
        **report,
        "interpretation": (
            "Each law was shown to reject a deliberate violation, so a clean "
            "verdict from this checker is evidence rather than assertion."
            if report["battery_discriminates"] else
            "The battery FAILED its negative control. Do not trust any clean "
            "verdict it produces until this is resolved."
        ),
    }


def tool_check_screening(c_full: list[list[float]],
                         c_iso: list[list[float]]) -> dict:
    """Check a coupling matrix against the many-body screening ceiling k <= 1."""
    import numpy as np
    from maxwell_lint import check_ceiling
    rep = check_ceiling(np.asarray(c_full, dtype=float),
                        np.asarray(c_iso, dtype=float))
    return {
        **rep.as_dict(),
        "summary": rep.summary(),
        "interpretation": (
            "No pair exceeds the screening ceiling; these predictions are "
            "physically admissible."
            if rep.passed else
            "This extraction predicts anti-screening (k > 1): adding a "
            "grounded conductor between two others would have to INCREASE "
            "their coupling. No passive arrangement of conductors in a linear "
            "medium can do that, so the extractor is wrong."
        ),
    }


def tool_pairwise_error(screening_factor: float) -> dict:
    """Relative error of assuming no screening, for a given screening factor."""
    import math
    if not (0.0 < screening_factor <= 1.0):
        raise ValueError("screening_factor must lie in (0, 1]")
    depth = -math.log10(screening_factor)
    err = 10.0 ** depth - 1.0
    return {
        "screening_factor_k": screening_factor,
        "screening_depth_delta": depth,
        "pairwise_relative_error": err,
        "pairwise_relative_error_pct": 100.0 * err,
        "interpretation": (
            f"A pairwise-superposition extractor, which assumes k = 1, is "
            f"{100*err:.2f}% wrong at this screening factor. The error is "
            f"E(delta) = 10^delta - 1: zero only when there is no screening, "
            f"one-sided (it never under-predicts), and strictly increasing in "
            f"depth -- so it worsens monotonically as an array densifies."
        ),
    }


TOOLS: dict[str, dict[str, Any]] = {
    "check_touchstone": {
        "fn": tool_check_touchstone,
        "description": (
            "Check whether an S-parameter (Touchstone .sNp) file describes a "
            "physically possible passive network. Verifies passivity, "
            "reciprocity, energy conservation, positive-real input impedance "
            "and non-negative group delay. Use this before reasoning from any "
            "S-parameter data you did not generate yourself."
        ),
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string",
                                    "description": "Path to a .sNp file"}},
            "required": ["path"],
        },
    },
    "self_test": {
        "fn": tool_self_test,
        "description": (
            "Verify the physics checker still discriminates, by confirming it "
            "rejects deliberately-invalid networks. Run this if you need to "
            "rely on a clean verdict."
        ),
        "schema": {"type": "object", "properties": {}},
    },
    "check_screening": {
        "fn": tool_check_screening,
        "description": (
            "Check a predicted coupling matrix against the many-body screening "
            "ceiling. Screening can only REDUCE coupling below the "
            "isolated-pair value, so a ratio above 1 is physically impossible."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "c_full": {"type": "array", "description": "NxN full-array coupling",
                           "items": {"type": "array", "items": {"type": "number"}}},
                "c_iso": {"type": "array", "description": "NxN isolated-pair baseline",
                          "items": {"type": "array", "items": {"type": "number"}}},
            },
            "required": ["c_full", "c_iso"],
        },
    },
    "pairwise_error": {
        "fn": tool_pairwise_error,
        "description": (
            "Given a screening factor k, return the relative error incurred by "
            "a pairwise-superposition extractor that assumes no screening."
        ),
        "schema": {
            "type": "object",
            "properties": {"screening_factor": {
                "type": "number",
                "description": "k = |C_full|/|C_iso|, in (0, 1]"}},
            "required": ["screening_factor"],
        },
    },
}


# ---------------------------------------------------------------- JSON-RPC

def handle(req: dict) -> dict | None:
    """Handle one JSON-RPC request. Returns None for notifications."""
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}

    def ok(result):
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": rid,
                "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok({
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "physics-lint-mcp", "version": __version__},
        })

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "tools/list":
        return ok({"tools": [
            {"name": n, "description": t["description"], "inputSchema": t["schema"]}
            for n, t in TOOLS.items()
        ]})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if tool is None:
            return err(-32602, f"unknown tool: {name}")
        try:
            result = tool["fn"](**args)
        except TypeError as exc:
            return err(-32602, f"invalid arguments for {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            # A physics failure is a RESULT, not a protocol error -- the agent
            # needs to see it, not receive an opaque transport error.
            return ok({"content": [{"type": "text", "text": json.dumps(
                {"error": f"{type(exc).__name__}: {exc}"}, indent=2)}],
                "isError": True})
        return ok({"content": [{"type": "text",
                                "text": json.dumps(result, indent=2)}]})

    if method == "ping":
        return ok({})

    return err(-32601, f"method not found: {method}")


def main(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": "parse error"}}
        else:
            resp = handle(req)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
