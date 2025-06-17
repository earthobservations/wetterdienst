---
file_format: mystnb
kernelspec:
  name: python3
---

# Command Line Interface

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.ui.cli import wetterdienst_help

print(wetterdienst_help)
```