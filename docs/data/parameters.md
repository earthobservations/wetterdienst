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

## Reading the provider tables

The parameter tables of the provider pages have five columns:

| Column | What it is |
| --- | --- |
| name | the canonical name, linked to the glossary below |
| original name | the provider's own name of the field, accepted wherever the canonical name is |
| description | what the field is, in the provider's words where it has them |
| unit | the unit the provider publishes the value in; `-` is dimensionless. The values come back in the unit of the quantity's target (see [Units](../usage/units.md)) unless conversion is switched off |
| constraints | the range the quantity has by its definition, see below |

**`constraints` is information for the reader, not a rule the library applies.** It is prose: nothing in the model
holds it, so a value outside it is not removed, flagged or refused, and a test can only hold the cells to one
grammar: `-` where none is stated, bounds as `>=lo` and `<=hi` joined by a comma (`>=0,<=100` for a percentage), and a
set of admissible codes as `∈ {0, 1, 2}`.

Read `>=0` as "by definition non-negative", not as "every value of this provider is". A reading can lie outside the
definition where the instrument or the water does it: the discharge of a tidal river runs backwards, and a snow gauge
reads a few centimetres below its zero (MeteoSwiss' gauge at station PLF reads -1 to -5 cm in 11 % of its hours).

What the library does enforce is another thing and is not this column. A source writes a missing value as a number
outside every range (`-999`); the provider's reader maps it to null and keeps the text the source wrote in the
`quality_flags` of the reading (`raw:-999`). Where a source also has values no instrument can produce (4021 degrees
for a daily maximum), its reader nulls those too, with a range per provider and resolution that is generous, since it
is there to catch a sentinel and not a record. Both are told in [Quality flags](../usage/python-api.md#quality-flags).

## Glossary

The unit type is a property of the parameter itself and decides which unit values are returned in;
the unit a given provider publishes is listed per provider under [providers](provider/index.md).

```{parameter-glossary}
```