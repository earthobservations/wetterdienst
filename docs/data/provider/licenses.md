# Licences and credit lines

Which licence each provider publishes its data under, and which credit line it asks for, in one table. Read this
before you publish anything built on the data. It is the maintainers' reading of what the providers state, not legal
advice, and it does not settle what a licence requires of you: that is for the licence and the provider's own terms,
which the licence column links.

The table is built from the same declarations that every answer of the library reports as `metadata.provider`
(`license` and `attribution`, see [response metadata](../../usage/restapi.md#response-metadata)) when these docs are
built, so it cannot differ from what you get back. A row has the networks that declare these terms; a provider whose
networks disagreed would have a row for each set. Each provider's page, linked in the first column, has a License
section that links its terms. Many say what the terms ask of you, in different detail (a credit line the terms
prescribe, a limit on use, a key); where one does not, the terms themselves are the source. What the project does with
the data (how it asks the providers, what it caches, what the hosted instance passes on, what the keys allow and what
the repository's own test files hold) is on [what wetterdienst does with the data](data-use.md).

```{provider-licenses}
```

- **Licence**: the SPDX identifier of the licence where it has one, else the name of the provider's own terms, linked
  to the licence or to the page of the provider that states it. "None stated by the provider" means that no terms
  could be found to name; ask the provider before you rely on its data.
- **Credit line**: the wording to give the source in, as the provider states it where it does, else its name as the
  rights holder. Give it wherever you publish the data or something made from it.

## What wetterdienst does to the data

(The rest, the cache and the hosted instance, is on [what wetterdienst does with the data](data-use.md).)

Licences such as CC BY ask that changes to the data be indicated. Wetterdienst changes it: the provider's files are
reshaped into one uniform table, parameters get one name whichever provider reports them, and values are converted to
common units. So every answer that holds provider data says so, in the same words for every provider and licence, in
`metadata.processing_note`:

> Processed by wetterdienst: the provider's data was reshaped into a uniform table, and its units converted where they differ.

The answers of `interpolate` and `summarize` add:

> The values were selected or calculated from the provider's readings.

and the headers of the climate stripes' image add:

> The image is drawn from the provider's annual values.

The values and the stations of the climate stripes carry the plain note: they are DWD's own annual values and a list
of its stations.

The note is information. It does not replace the credit line of the provider, and it does not say what your licence
asks of you when you pass the data on: if you publish the data or a chart of it, say that it was processed, in your
own words, next to the credit line.

**Where the note goes.**

- The `metadata` block of every JSON, GeoJSON and NDJSON answer of the REST API, the MCP server and the command line,
  and the `X-Wetterdienst-Processing` header of every REST answer, CSV and images included.
- Python: the `metadata` of `to_dict`, `to_json` and `to_ogc_feature_collection` with `with_metadata=True`.
- Files the library writes: in a Parquet file, a NetCDF file and a Zarr group (a key of its own and in the block), and
  in the `<file>.metadata.json` beside any other file written with `with_metadata=True`.

**Where it does not go.**

- A CSV, spreadsheet, JSON, JSON Lines, GeoJSON or Feather file written without `with_metadata=True`: it holds the
  records and nothing else. Give the credit line and say the data was processed where you publish it.
- The command line's CSV output and the image file `stripes image` writes: neither has a place for it.
- The web app does not show it yet (tracked in [#3799](https://github.com/earthobservations/wetterdienst/issues/3799)).
- The answers of `providers` and `coverage`, which describe the library and its networks and hold no provider's data.
  The list of run times of `issues` and the warnings of `alerts` do carry it.

## Keeping it true

The licence links of the table are external links of these docs, so `uv run poe "docs:linkcheck"` (run weekly by the
`Docs` workflow) fails on one that is dead. A provider changing its terms without moving the page is not noticed by a
machine, so a [report of a provider whose terms differ from what is stated here](https://github.com/earthobservations/wetterdienst/issues)
is welcome.
