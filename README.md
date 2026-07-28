# physics-lint-mcp

![CI](https://github.com/nickharris808/physics-lint-mcp/actions/workflows/ci.yml/badge.svg) ![MCP](https://img.shields.io/badge/MCP-2024--11--05-purple) ![Licence](https://img.shields.io/badge/licence-Apache--2.0-green) ![Tests](https://img.shields.io/badge/tests-23%20passing-brightgreen)

**A physics oracle your AI agent cannot talk its way past.**

An LLM has no way to distinguish a physically impossible S-parameter matrix from
a plausible one — both are just numbers. Hand an agent a fabricated model and it
will reason confidently about it, cite it, and build on it. Nothing in the loop
objects.

These MCP tools give the agent ground truth from linear algebra instead of from
its own judgement.

## 30-second quickstart

```bash
# from source (works today)
git clone https://github.com/nickharris808/physics-lint-mcp.git
pip install ./sparam-lint ./maxwell-lint ./physics-lint-mcp
```

> **Not yet on PyPI.** `pip install physics-lint-mcp` is the intended install
> once published.

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

| Tool | What it answers |
|---|---|
| `check_touchstone` | Is this `.sNp` file a physically possible passive network? |
| `check_screening` | Does this coupling matrix violate the many-body screening ceiling? |
| `pairwise_error` | How wrong is a pairwise extractor at this screening factor? |
| `self_test` | Does the checker still discriminate? |

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
