# fact_type validation

## Problem
`write_memory` accepts `fact_type` as a free string and stores whatever it is
given. The agent's tool schema declares the four values as a JSON-schema enum,
so that path is constrained at the API layer. Consolidation is not: it passes
the extractor's raw JSON straight through.

The failure is quiet. An unrecognised value never matches the core-memory
filter, so a fact the model meant as a `constraint` never reaches the
always-in-context block and nothing reports it. It also breaks the assumption
every aggregation over the field relies on.

Live corpus is currently clean (preference 72, identity 70, world 36,
constraint 33), so this is preventive, not a repair.

## Scope
Not addressed here: a well-formed but wrong type (a transient status typed
`identity`). That is a judgment error, not a format error, and no validator
can catch it.

## Todo
- [x] `VALID_FACT_TYPES` + `DEFAULT_FACT_TYPE` in constants.py
- [x] `_clean_fact_type()` in operations.py, following `_clean_date`'s precedent
- [x] Call it from `write_memory`
- [x] Tests
- [x] Full suite + live check

## Review

Added `VALID_FACT_TYPES` and `DEFAULT_FACT_TYPE` to constants.py, and
`_clean_fact_type()` to operations.py, called from the one place semantic
documents are built. Three files touched plus tests.

Case and whitespace are normalised. Anything else falls back to `preference`
with a logged warning. The fallback is deliberately the one type that is never
injected into the system prompt, so an unrecognised value cannot be promoted
into every future turn on a guess. A misspelling is not repaired to its nearest
valid neighbour for the same reason.

Never raises, following `_clean_date`: a bad field should not cost the whole
consolidation pass.

204 tests passing (was 183). Verified live: `"constraints"` stored as
`preference` and stayed out of the profile block; `"  Identity  "` normalised
and appeared in it.

Not addressed: a valid-but-wrong type. That is a judgment error and no
validator catches it.
