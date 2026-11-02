---
type: llm
focus: trace
weight: 1
---

At least two different user errors (such as an unknown expense id, nothing to change, an unknown category or an invalid amount) are asserted with pytest.raises(IBudgetError, match=...).
