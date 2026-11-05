# Licences and credit lines

Which licence each provider publishes its data under, and which credit line it asks for, in one table. Read this
before you publish anything built on the data. It is the maintainers' reading of what the providers state, not legal
advice, and it does not settle what a licence requires of you: that is for the licence and the provider's own terms,
which the licence column links.

The table is built from the same declarations that every answer of the library reports as `metadata.provider`
(`license`, `attribution` and `notice`, see [response metadata](../../usage/restapi.md#response-metadata)) when these
docs are built, so it cannot differ from what you get back. A row has the networks that declare these terms; a
provider whose networks disagreed would have a row for each set. Each provider's page, linked in the first column,
keeps the clauses that matter, quoted, and the terms beyond the licence (rate limits, a required `User-Agent`, keys).

```{provider-licenses}
```

- **Licence**: the SPDX identifier of the licence where it has one, else the name of the provider's own terms, linked
  to the licence or to the page of the provider that states it. "None stated by the provider" means that no terms
  could be found to name; ask the provider before you rely on its data.
- **Credit line**: the wording to give the source in, as the provider states it where it does, else its name as the
  rights holder. Give it wherever you publish the data or something made from it.
- **Notice**: a restriction in the provider's terms, beyond the licence and the credit line, that you have to know
  of. Today that is ECCC's, below. A notice informs: nothing is refused or switched off for it.

## What wetterdienst does to the data

Licences such as CC BY ask that changes to the data be indicated. Wetterdienst changes it: the provider's files are
reshaped into one uniform table, parameters get one name whichever provider reports them, and values are converted to
common units. So every answer says so, in the same words for every provider and licence, in `metadata.processing_note`
(and in the `X-Wetterdienst-Processing` header, the `processing_note` of the file a result is written to and of the
sidecar next to it):

> Processed by wetterdienst: the provider's data was reshaped into a uniform table and its units were converted (unless turned off).

The answers of `interpolate`, `summarize` and the climate stripes add that the values are derived, calculated by
wetterdienst from readings and not the provider's own values:

> The values are derived: wetterdienst calculated them from the provider's readings, they are not the provider's own values.

The note is information. It does not replace the credit line of the provider, and it does not say what your licence
asks of you when you pass the data on: if you publish the data or a chart of it, say that it was processed, in your
own words, next to the credit line. A [file or an image](../../usage/export.md) carries the note where its format has
a place for it, and a CSV, a spreadsheet or an image has none (the headers of the REST answer, the `--with-metadata`
file beside it and the command line's JSON have it).

## ECCC

ECCC's licence agreement allows its data to be passed on only under conditions, quoted on its
[provider page](eccc/index.md#license): no fee for the data itself, and every recipient agrees to the same
restrictions before use. Wetterdienst serves ECCC data, as it serves the data of every provider, on the hosted instance
and through the library, so every answer for ECCC carries the notice:

> ECCC data may be passed on only if every recipient agrees to the same restrictions, and no fee is charged for the data itself. If you pass it on, pass these terms on: https://climate.weather.gc.ca/prods_servs/attachment1_e.html

If you build on ECCC data and pass it on, read the agreement first. Whether the use the hosted instance makes of the
data, serving it through the REST API, the MCP server and the app, is within the agreement is not settled, and so is
which of ECCC's two texts covers it (the [provider page](eccc/index.md#license) has both); this page will say what
ECCC states on it.

## Keeping it true

The licence links of the table are external links of these docs, so `uv run poe "docs:linkcheck"` (run weekly by the
`Docs` workflow) fails on one that is dead. A provider changing its
terms without moving the page is not noticed by a machine, so a [report of a provider whose terms differ from what is
stated here](https://github.com/earthobservations/wetterdienst/issues) is welcome.
