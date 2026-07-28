# physics-lint-mcp

![CI](https://github.com/nickharris808/physics-lint-mcp/actions/workflows/ci.yml/badge.svg) ![MCP](https://img.shields.io/badge/MCP-2024--11--05-purple) ![Licence](https://img.shields.io/badge/licence-Apache--2.0-green) ![Tests](https://img.shields.io/badge/tests-28%20passing-brightgreen)

**A physics oracle your AI agent cannot talk its way past.**

An LLM has no way to distinguish a physically impossible S-parameter matrix from
a plausible one — both are just numbers. Hand an agent a fabricated model and it
will reason confidently about it, cite it, and build on it. Nothing in the loop
objects.

These MCP tools give the agent ground truth from linear algebra instead of from
its own judgement.

## 30-second quickstart

```bash
git clone https://github.com/nickharris808/physics-lint-mcp.git
cd physics-lint-mcp

pip install git+https://github.com/nickharris808/sparam-lint.git@main \
            git+https://github.com/nickharris808/maxwell-lint.git@main \
            .
```

The two checkers are separate packages and are pulled from their own
repositories; the server is the `.` at the end. Confirm the server answers over
stdio before wiring it into a client:

```bash
$ printf '%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  | physics-lint-mcp | tail -1 | python3 -m json.tool | grep '"name"'
                "name": "check_touchstone",
                "name": "self_test",
                "name": "check_screening",
                "name": "pairwise_error",
```

> **Not yet on PyPI.** `pip install physics-lint-mcp` is the intended install
> once published; until then the three-package command above is the one that
> works.

## Configure

Claude Desktop / Cursor / any MCP client:

```json
{
  "mcpServers": {
    "physics-lint": {
      "command": "physics-lint-mcp"
    }
  }
}
```

A ready-made [`mcp.json`](mcp.json) ships with the package.

## Tools

| Tool | Arguments | What it answers |
|---|---|---|
| `check_touchstone` | `path` *(string, required)* | Is this `.sNp` file a physically possible passive network? |
| `check_screening` | `c_full` *(array, required)*, `c_iso` *(array, required)* — both N×N | Does this coupling matrix violate the many-body screening ceiling? |
| `pairwise_error` | `screening_factor` *(number, required)*, `k` in (0, 1] | How wrong is a pairwise extractor at this screening factor? |
| `self_test` | none | Does the checker still discriminate? |

The schemas the server advertises over `tools/list` are the authoritative
version of that table, and a test asserts the two agree.

## A worked example: an agent that cannot fool itself

The failure this prevents is specific. An agent is handed a vendor `.s2p`, is
asked whether the link will close, and reasons fluently about numbers that
describe a network which cannot exist. Nothing in the loop objects, because an
LLM has no way to tell an impossible S-matrix from a plausible one.

Wire the server in, and the first thing worth doing in a session is asking the
checker to prove itself:

> **You:** Before we look at the model, run `self_test`.
>
> **Agent:** *(calls `self_test`)* The battery discriminates — five networks
> built to violate one law each were all rejected.

Now the model:

> **You:** Check `vendor/lna_stage.s2p`.
>
> **Agent:** *(calls `check_touchstone` with `path="vendor/lna_stage.s2p"`)*
> This network is not physically realizable as a passive device: it fails
> passivity and energy conservation. I will not reason from its values.

That last sentence is not the agent being careful — it is the `interpretation`
field coming back in the result, written for a model to read. An agent given
only `{"passed": false}` will often keep going.

Two things the design forbids, and both matter more than they look: the agent
**cannot repair** the model, because every tool is read-only; and it **cannot
mistake a failure for a crash**, because a physics failure comes back as a
result rather than a transport error. The next three sections are those two
properties in detail, and the third is the case that will bite you first.

## Troubleshooting

**`physics-lint-mcp: command not found`** — the console script did not install.
Check `pip show physics-lint-mcp`; if it is there, the environment's `bin`
directory is not on `PATH`, which is common when a client launches the server
with a different shell. Use the absolute path in `mcp.json`:
`{"command": "/full/path/to/venv/bin/physics-lint-mcp"}`.

**The client shows the server as failed to start** — run the stdio smoke test
from the quickstart by hand first. It is the same code path with none of the
client's supervision, so the traceback is visible.

**`No module named 'sparam_lint'`** — the two checkers are separate packages and
are not pulled in automatically. Install all three, as the quickstart shows.

**A tool call returns `isError: true` and the agent stops** — that is a physics
verdict, not a fault. The result carries the failed laws and an interpretation;
your agent should read them rather than treat the call as failed.

**Nothing at all comes back** — the server speaks JSON-RPC over stdio, one
object per line. A client that batches several objects into one line, or that
writes without a trailing newline, will hang. The `initialize` request must
come first.

**The tool list is shorter than the table above** — you are running an older
build. `tools/list` is generated from the same definitions the table is tested
against, so they cannot disagree within one version.

## What the agent sees

Every result carries an `interpretation` field written **for a model to read**,
because an agent acts on prose, not on a boolean:

```json
{
  "physically_admissible": false,
  "failed_laws": ["passivity", "energy_conservation"],
  "interpretation": "This network is not physically realizable as a passive
    device. Do not use it as a reference and do not reason from its values.
    One legitimate exception: a non-reciprocal device such as a ferrite
    isolator will correctly fail the reciprocity law by design."
}
```

That last sentence matters. An agent told only "reciprocity failed" will helpfully
"fix" a perfectly good isolator.

And on a clean result the interpretation says what the verdict does **not** mean:

> All five laws hold; the network is physically admissible. Note this does NOT
> mean it is accurate — a passive model of the wrong structure passes every law
> here.

## Every tool is read-only

Nothing here writes, fabricates, or repairs a model. An agent that could
silently patch a failing network would defeat the purpose of having an oracle,
so the absence of I/O is enforced by a test.

## A physics failure is a result, not an error

A file that fails the laws returns a normal result with `isError: true` and the
full verdict, rather than a transport-level error. The agent needs to *see* the
failure to reason about it; an opaque protocol error teaches it nothing.

## Try it without an agent

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | physics-lint-mcp
```

## Scope, honestly

These tools verify **physical admissibility, not accuracy**. A passive model of
entirely the wrong structure passes every check. They are a floor, not a
substitute for validation against a field solve or measurement.

## The rest of the toolkit

Eight artifacts that answer one question in different places: **is this
model physically possible?** Each is a grader — it can tell you a model is
wrong; none can tell you one is right.

| | |
|---|---|
| [`sparam-lint`](https://github.com/nickharris808/sparam-lint) | Is an S-parameter model physically possible? Five laws + a negative control. |
| [`maxwell-lint`](https://github.com/nickharris808/maxwell-lint) | Does a coupling extractor predict impossible physics? Screening ceiling k ≤ 1. |
| [`abstain-bench`](https://github.com/nickharris808/abstain-bench) | Does a model know when to shut up? Abstention recall, never pooled with accuracy. |
| [`sparam-conformance`](https://huggingface.co/datasets/nickh007/sparam-conformance) | 11 labelled networks with verified ground truth. Grades the graders. |
| [`screening-ceiling`](https://huggingface.co/datasets/nickh007/screening-ceiling) | A certified impossibility result + 27 counterexamples. Zero-dependency verifier. |
| [`physics-lint-action`](https://github.com/nickharris808/physics-lint-action) | The same checks, in your CI. |
| [`physics-lint-mcp`](https://github.com/nickharris808/physics-lint-mcp) ← you are here | A physics oracle your AI agent can call. |
| [**Try it in your browser**](https://huggingface.co/spaces/nickh007/physics-lint) | All three checks, no install, runs client-side. |

These tools **grade** a model. Producing one that is passive *by
construction* — so it cannot fail these laws whatever its parameters — and
accurate at speed in the many-body regime, with calibrated abstention and a
fail-closed signoff certificate, is the commercial core:
**[ChipletOS](https://chipletos.com)**.

## Licence

Apache-2.0. See [LICENSE](LICENSE); copyright in [NOTICE](NOTICE).

The signoff certificate and passive-by-construction synthesis these tools were
written alongside are the [ChipletOS](https://chipletos.com) closed core.
