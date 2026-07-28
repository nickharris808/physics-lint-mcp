# Contributing to physics-lint-mcp

## Tools stay read-only

No tool may write, mutate, or repair anything. There is a test asserting the
server performs no file I/O. An agent that could silently "fix" a failing model
would destroy the value of having an oracle at all.

## Every tool needs an `interpretation`

Agents act on prose. A bare boolean gets misread — an agent told only
"reciprocity failed" will helpfully "fix" a legitimate ferrite isolator. State
what the verdict means, what it does **not** mean, and the known exceptions.

## Physics failures are results, not protocol errors

If a network fails the laws, return a result with `isError: true` and the full
verdict. Reserve JSON-RPC error codes for genuine protocol problems: unknown
method, unknown tool, malformed arguments.

## Testing

Test at the JSON-RPC layer, not by calling the Python functions — the protocol
surface is what an agent actually touches.

```bash
pip install -e ".[dev]"
pytest -q
```
