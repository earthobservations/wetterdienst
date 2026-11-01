# Data

What is served, by whom and under which terms: the [overview](overview.md) of the providers, the
[parameters](parameters.md) (what each quantity is and its unit), the [quality flags](quality-flags.md) that come
with a reading, the [special values](special_values.md) (a calm, a trace, an obscured sky, a missing value) and the
one rule each is read to, the [plausibility checks](plausibility.md) that keep or null a number no sensor can have
produced, how a [timestamp is to be read](time_reference.md) for each provider, and a page for every
provider, with its networks, resolutions, datasets and the parameter tables.

The licence of the data and the credit line to give are part of every answer of the REST API
(`metadata.provider`), and each provider's page links the terms: check them before you publish anything built on
the data.

```{toctree}
:hidden:

overview.md
parameters.md
quality-flags.md
special_values.md
plausibility.md
time_reference.md
provider/index.md
```
