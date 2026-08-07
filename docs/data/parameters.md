---
file_format: mystnb
kernelspec:
  name: python3
---

# Parameters

The data that is provided via `wetterdienst` and its implemented services comes in all kinds of different shapes. Every
provider publishes its own parameter codes, so each one is mapped onto a canonical parameter name that means the same
thing everywhere. Those names, and the unit type each of them implies, live in a single table
(`wetterdienst.metadata.parameter_table`) that every provider's metadata is tested against, so a name cannot mean two
different quantities depending on who reported it.

The glossary below lists them all. The provider pages link into it, so from any provider's parameter table you can jump
to what the parameter actually is.

## Metadata Model

Import the provider specific metadata model like:

You can inspect the metadata model of the services to see the available parameters and their descriptions. The metadata 
model is a Pydantic model with all its functionality so you can also extract a JSON schema.

Each parameter carries only what the provider itself knows -- the canonical `name`, the provider's own `name_original`
and the `unit` it publishes in. The unit type is not repeated here because it follows from the canonical name; look it
up in the glossary below, or in `wetterdienst.metadata.parameter_table`.

```{code-cell}
---
mystnb:
  number_source_lines: true
---
from wetterdienst.provider.dwd.observation import DwdObservationMetadata

metadata = DwdObservationMetadata.model_dump_json(indent=2)
print(metadata)
```

## Glossary

The unit type is a property of the parameter itself and decides which unit values are returned in;
the unit a given provider publishes is listed per provider under [providers](provider/index.md).

```{parameter-glossary}
```