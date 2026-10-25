# Writing the documentation

How the pages are organised, what is checked by a test, and the conventions that keep them one voice.

## Where a page goes

| Section | What is in it | Audience |
| --- | --- | --- |
| Get started (`usage/quickstart.md`, `concepts.md`, `troubleshooting.md`) | the shortest path to a first call on every surface, the words, what a failure means | a new user |
| Usage (`usage/`) | how to do something: one page per task or surface (Python, command line, REST API, MCP, app, export, scheduling, Docker) | a user |
| Data (`data/`) | what is served: the overview, the parameter glossary, the quality flags, the time zones, one page per provider and network | a user choosing data |
| Reference (`library/`, `changelog.md`, `known_issues.md`) | the API generated from the docstrings, the history, problems of one machine | a user looking something up |
| Project (`contribution/`) | how to work on the code, add a provider, write these pages | a contributor |

A page is a tutorial, a how-to, a reference or an explanation, and says which by what it opens with; do not mix them
within a page where a link will do. A fact is told once and linked from the other places: the REST page owns the
problem types and the limits, the settings page the settings and options, the CLI page (generated from the help) the
options. A page that moves leaves a heading behind, so that the links to its sections still land somewhere: the app
links to `restapi.html#mcp-endpoint`, and the README and PyPI to the pages by name.

## Samples

Show the simplest call first and add one idea per sample. The same example data runs through the pages: DWD
observation, the daily `climate_summary`, `temperature_air_mean_2m`, station `01048` (Dresden-Klotzsche), and the
default address of the API, `localhost:7890`.

- A `{code-cell}` is run when the pages are built and its output is shown; use it where the output is the point. It
  needs the network. A cell that fails fails the build, unless the provider did not answer
  ([below](#cells-that-fail)); its traceback is shown in the page, so read the built page, not only the log.
- Every Python block of a page is run by `tests/test_docs_samples.py` (marker `remote`), in order and in one
  namespace, as the notebook pages are, so a block may use what an earlier one defined. A statement that is meant to
  fail says so in the comment before it, `# raises InvalidParameterError`; a block that cannot run (an InfluxDB that is
  not there) is named in `NOT_RUN` of that test, with the reason.
- Every `wetterdienst ...` command is parsed by the command line itself, and every `http` or `curl` request is checked
  against the OpenAPI document, offline. A renamed option fails the test, so the pages cannot keep it.
- A table printed in a comment is compared with what the statement prints; write only cells the result has.
- A JSON sample the REST page shows has the members the code has (`{...}` leaves an object out).

## What is tested, so that it need not be re-read

`tests/test_docs.py` holds the provider pages to the metadata (resolutions, datasets, parameters, units, descriptions),
the settings and options tables to `Settings` and `Options` (names and defaults), the limits table to the settings, the
environment variables and extras named to those that exist, the formatter table to the signatures and the overview to
the registry. `tests/test_docs_samples.py` holds the samples. Add a check to one of them when you write a table of
something the code knows; prefer that to a sentence that has to be remembered.

## Numbers and names

- Do not write a count that changes without a change of ours: the stations of a provider, the files of a source. Say
  "more than 5000" or leave it out. A count the code states (providers, parameters of a dataset) is tested or derived.
- Use the canonical parameter names and the vocabulary of the REST API (underscores) and the command line (hyphens),
  see [one vocabulary](../usage/restapi.md#one-vocabulary).
- State what the code does, not what was meant: check the sentence against the code before it goes in, and re-read the
  whole claim when you edit one that is there.

## Links

Link pages by their path (`[Settings](settings.md#python)`), and to a heading no deeper than the third level, which
are the ones with an anchor. External links are checked weekly by `docs.yml` (`poe "docs:linkcheck"`); a pull request
builds the pages with warnings as errors, so a broken link or an unreadable directive is a red check.

## Cells that fail

Read the Docs does not fail a build for a warning, and myst-nb shows a failed cell and goes on, so a cell that raised
`MissingDependencyError` was published until somebody read the page. `docs/_ext/notebook_errors.py` closes that. The
notebooks run with `nb_execution_allow_errors`, so that every cell runs, and the extension reads the error outputs of
each executed notebook (the cells that hide their output included) and judges them when the build is done:

- A provider that did not answer is a warning (`wetterdienst.outage`, which `suppress_warnings` can silence): the page
  shows the traceback and the build goes on. What counts is the rule of `skip_if_upstream_unavailable` in
  `tests/conftest.py`: a `NoInternetError` whose connection timed out, was refused or reset or had no route, and a
  `DownloadError` caused by a timeout, a dropped connection, a body cut short or a 5xx. A 404 or another 4xx is the
  provider answering, and a name that does not resolve is what a decommissioned host looks like, so those fail, and so
  does a `DownloadError` of any other cause (TLS, a refused redirect). `tests/test_docs_notebook_errors.py` holds the
  two to the same answer.
- A cell that is interrupted by `nb_execution_timeout` is a warning too: a slow provider must not fail the build. A
  hang in our own code looks the same and is not told apart, so read the warning.
- A `NameError` after one of these on the same page is the cell that failed leaving a name undefined, and is not
  judged. Any other error after it is.
- Any other exception fails the build (the exit status is 1) after all pages are written, with an error naming each
  page and line. The built page is stale until it is read again: after a change of code, build with `-E` or run
  `poe "docs:clean"` first.
- A cell that is meant to fail carries the tag `raises-exception` (`:tags: [raises-exception]` under the directive) and
  is not looked at. A sample that shows a failure is better caught in a `try` block.

A build with `-D nb_execution_mode=off`, as `docs.yml` runs it, executes no cell, so it neither needs the network nor is
it checked by this. The notebook is judged as myst-nb hands it on, after it ran or was restored from its cache; with
`nb_execution_mode=cache` the notebook of a page with a failed cell was not stored (myst-nb 1.4, jupyter-cache), so it
runs again, and Read the Docs builds with the default `auto` anyway. A page that is executed inline
(`nb_execution_mode=inline`) is not checked. `docs.yml` runs `tests/test_docs_notebook_errors.py` with the docs group,
which is where the glue to myst-nb and Sphinx is held; elsewhere the tests of the glue are skipped.

## Building

```bash
uv run poe docs            # as Read the Docs builds it: the notebook pages are executed, which needs the network
uv run poe "docs:linkcheck"
uv run poe "docs:clean"
uv run pytest tests/test_docs.py tests/test_docs_samples.py            # offline
uv run pytest -m remote tests/test_docs_samples.py                     # runs the Python samples
```

## Changelog

An entry in `CHANGELOG.md` is for a page that stated something wrong, not for a new or reorganised page.
