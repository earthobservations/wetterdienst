---
file_format: mystnb
kernelspec:
  name: python3
---

# Command Line Interface

A `--stations` list leaves out an id the network has no station for and says so in a warning. A boolean
option is the same everywhere: bare, as `--pretty`, or as `--pretty=true` and `--pretty=false`. The command line
and the [REST API](restapi.md) render a result through the same function, so the same request gives the
same output, the `metadata` block of the [response metadata](restapi.md#response-metadata) and a
`settings` block with `--with-metadata` included.

The plausibility checks each have an option, `--plausibility-range`, `--plausibility-elevation`, `--plausibility-stuck`,
`--plausibility-consistency`, `--plausibility-floor`, `--plausibility-limits`, `--plausibility-source`, `--plausibility-step` and `--plausibility-relations`, which take `hard` (null the value, keep the number as
`rejected:<check>,raw:<number>` in `quality_flags`) or `soft` (keep the value, flag it `suspect:<check>`), and
`WD_TS_PLAUSIBILITY__<CHECK>` sets one for a host. One not given keeps the host's mode, or its default (`stuck`, `step`, `source` and `relations` are soft,
the others hard). `--plausibility soft` (or `hard`) sets all of them at once, and a check given beside it wins whatever the
order: `--plausibility soft --plausibility-range hard`; `WD_TS_PLAUSIBILITY=soft` does it for a host. A forecast network (`dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`: `kind` `forecast`) is judged soft in every check but `floor` and `limits`, whatever is given: `hard` there is still flagged `suspect:<check>`, never nulled (`limits` follows its mode). `--plausibility-source` is the verdict of the source's own quality flag (GHCN-Daily `QFLAG`, Frost `qualityCode` 7, an
Environment Agency `Suspect`, DMI `validity:false`, ...): soft by default, it keeps the value and adds `suspect:source`, and `hard`
nulls it as `rejected:source,raw:<text>`, except the suspect level of a source that has two (GHCNh `Suspect` and source 382 `R`, CHMI `Suspect`, MADIS `Questioned`, GHCNh `f`), which stays
`suspect:source`. See [plausibility checks](../data/plausibility.md).

```bash
wetterdienst values --provider=dwd --network=observation --parameters=hourly/moisture/pressure_air_site \
    --stations=01048 --timestamp=2024-01 --plausibility-range=soft --plausibility-stuck=hard

# everything the source wrote, flagged: every check soft but the range
wetterdienst values --provider=dwd --network=observation --parameters=hourly/moisture/pressure_air_site \
    --stations=01048 --timestamp=2024-01 --plausibility=soft --plausibility-range=hard
```

`--limits` sets bounds of your own for the check `limits`: `name=low:high`, an end left empty for none, or a JSON object
of `[low, high]` pairs, repeated for more parameters. A name is a canonical parameter (every dataset that serves it) or
`resolution/dataset/parameter` (that dataset only, which wins where both name a parameter), and a bound is in the unit
the values come back in (`--unit-targets`, or the source's unit with `--convert-units=false`). A value outside is null
with `rejected:limits,raw:<number>`, or with `--plausibility-limits=soft` kept and flagged `suspect:limits`; a forecast
network follows the mode too. `WD_TS_LIMITS` (JSON) sets them for a host, and a name given on the command line replaces
the host's for that name. An unknown name, a pair with `low` above `high` and a bound that is not a number are a usage
error.

```bash
# null a mean temperature outside -30 to 45 degrees and a daily rain above 200 mm, keeping the number as `raw:`
wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
    --stations=01048 --timestamp=2024-01 --limits=temperature_air_mean_2m=-30:45 --limits=precipitation_amount=:200

# the same, in degrees Fahrenheit and for the daily dataset only, as JSON
wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --stations=01048 --timestamp=2024-01 \
    --unit-targets='{"temperature": "degree_fahrenheit"}' \
    --limits='{"daily/climate_summary/temperature_air_mean_2m": [-22, 113]}'
```

The command line has none of the limits of the REST API on the rows or stations of a request. A long record or a
whole network is written with `--target` to a file or a database, see
[Getting more than the limit](large-requests.md#leave-the-server).

## Logging

The data a command writes goes to stdout, and what it says about them to stderr as log lines: the warnings about the
answer (values a plausibility check rejected, markers of the source that were nulled, a file the provider let go, a
station `skip_empty` left out, a parameter without rows, a station id left out), the progress of a long request, other
warnings and notes, and the errors. Each warning that counts something over the request, as the values a check
rejected, is one line with its total when the values are in. A command that has `--debug` has `--quiet` beside it, but
`restapi`. `--debug` adds the debug lines of the package, and `--quiet` leaves **the errors and the warnings about the
answer**:

```bash
# a scheduled job: nothing on stderr unless it failed, the answer is not whole or nothing was written
wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --stations=01048 \
    --timestamp=2024-01 --target=file://values.json --quiet
```

`--quiet` changes the level of the log and nothing else: stdout holds what it held (a `--target` is written as without
it), a failure is still written (a line for a provider that cannot be reached, a missing credential or extra; a
`--target` that cannot be written is the traceback it is without `--quiet`), a usage error is still click's and the exit
code is the one the command would have had, `0`, `1` or `2`.

What it keeps besides the errors are the warnings that qualify the answer, the lines that are also in the `warnings` of
the `metadata` block of JSON and GeoJSON output (see [response metadata](restapi.md#response-metadata)): they tell a
partial answer from a whole one, and CSV and a file `--target` carry no such block, so stderr is where a script reads
them. It keeps one more sentence, `Nothing was written to --target.`, which a command that found no data to write to its
`--target` says: a scheduled run that wrote nothing must not look like one that did (the `--target` is left as it
was, and the exit code is `0`). What it drops is the progress, the notes (the cache that is enabled), the other warnings
of the package and everything the libraries underneath write below an error, among them the sentence that a request
returned no data or no stations: an empty answer is empty on stdout. The libraries behind an image (Kaleido, its
browser) are kept at warnings for good, since they write what they cleaned up as the process ends. `--quiet` and
`--debug` are a usage error together, `--quiet=false` being no `--quiet`. The server, `restapi`, has `--debug` alone:
its log is also uvicorn's, which `--quiet` would not reach.

## Colour

The command line writes no colour of its own: its help, its errors, the log and the data have no escape code,
on a terminal, in a pipe, and where `FORCE_COLOR` asks for it (a test holds all of it to that). Two things outside it
can: Python colours the traceback of a defect on a terminal (3.13 and later), and uvicorn the level of the log lines of
`wetterdienst restapi`. [`NO_COLOR`](https://no-color.org) set to anything but the empty string turns both off, and
a command that is not on a terminal is plain without it.

```bash
NO_COLOR=1 wetterdienst restapi
```

## Shell completion

Completion is click's own, for bash (4.4 or later: not the 3.2 that macOS has in `/bin/bash`), zsh and fish. It
completes the commands, their options, the choices of an option and, from the registry of providers, `--provider` and
`--network` (the networks of the `--provider` before it on the line, else all of them). It does not complete `--parameters`,
`--stations` or `--timestamp`: those would take the provider's metadata or its station list, a provider's import
and possibly the network, which a TAB must not do. Every TAB is a process that imports the command line, which takes
under 0.1 s on a laptop (`--help` and `--version` as well: the settings, polars and the providers are imported by the
command that uses them) and never contacts a provider.

Complete a value with a space, as `--provider dw` and then TAB. The `--provider=dw` spelling the examples use is not
completed: zsh would replace the whole word with `dwd`, and bash offers nothing after the `=` (the provider before it
still narrows `--network`).

Print the script once, put it where the shell reads it, and start a new shell:

```bash
# bash: ~/.bashrc
eval "$(_WETTERDIENST_COMPLETE=bash_source wetterdienst)"
# zsh: ~/.zshrc, after compinit
eval "$(_WETTERDIENST_COMPLETE=zsh_source wetterdienst)"
# fish
_WETTERDIENST_COMPLETE=fish_source wetterdienst > ~/.config/fish/completions/wetterdienst.fish
```

The `eval` form runs `wetterdienst` every time a shell starts, which costs that time each time. To keep the start
quick, write the script to a file once and source that, and again after an upgrade:

```bash
_WETTERDIENST_COMPLETE=bash_source wetterdienst > ~/.wetterdienst-complete.bash
echo 'source ~/.wetterdienst-complete.bash' >> ~/.bashrc
```

There is no `wetterdienst completion` command: the variable is the whole of it, and a command would be a surface to
keep for what the variable does. PowerShell and the Windows shell are not supported by click.

## Exit codes

What the command line promises across releases, its options and exit codes among it, is on the
[Compatibility](compatibility.md#command-line) page.

The exit code of a command is part of its contract, for the script, the scheduler and the CI job that branch on
it: it is `0`, `1` or `2`, and no command has another. A test holds every explicit exit and every error the
command line raises to these three, and each failure of the library to the status the REST API answers it with.

| Code | Meaning | REST | For instance |
| --- | --- | --- | --- |
| `0` | an answer, empty or not | 200 | the values; a window without readings, a name nothing is called or an id the network has no station for (the sentence is on stderr, and a `--target` is left as it is); `--help`, `--version` |
| `1` | a failure that is not the request's to rephrase | 5xx | a provider that failed or cannot be reached (`DownloadError`, `NoInternetError`), an image the browser did not draw in time (`ImageTimeoutError`), a credential or an extra the machine lacks, a malformed `WD_*` setting, a `--target` that cannot be written, a defect, Ctrl-C |
| `2` | a request that cannot be served as phrased | 400, 404, 422 | no command or an unknown one, an unknown or missing option, a value out of range, a selection that is not exactly one, a provider, network or station that does not exist, a window that ends before it starts |

What the REST API answers with a 400, 404 or 422 is `2` here, and what it answers with a 5xx is `1`, so the
same request fails with the same kind of code on both. A failure of the provider and a defect of ours are both
`1`: a script cannot tell them apart by the code, and reads the message. The three codes are frozen -- a code of
its own for an upstream failure would break the scripts that test for `1` -- and a change to one is a breaking
change of the command line. A command that a signal ends, or an interpreter that crashes as it exits
(see [known issues](../known_issues.md)), has the status the operating system gives it.

An option is spelled as the REST query parameter and the MCP argument of the same request, with hyphens
for underscores (`--name-threshold` is `name_threshold`), and a list is plural and comma-separated
(`--stations=01048,04411`). The names the options had before, `--convert_units`, `--station` for a list
and the like, fail with an error naming the new one. See [one vocabulary](restapi.md#one-vocabulary).

`stations` has no `--lead-time` and `--issue`: the stations of a forecast network do not depend on the run,
which is chosen for the values, so pass them to `values`. `wetterdienst stations --lead-time=long` fails
with click's `No such option`.

Every command's help, as `wetterdienst COMMAND --help` prints it: its options and, for most, examples
to start from. Rendered when the documentation is built, so it names the options the release has.

```{code-cell}
---
tags: [remove-input]
---
import click

from wetterdienst.ui.cli import cli


def print_help(command: click.Command, path: list[str], parent: click.Context | None = None) -> None:
    ctx = click.Context(command, info_name=path[-1], parent=parent, max_content_width=100, terminal_width=100)
    print(f"$ {' '.join(path)} --help\n")
    print(command.get_help(ctx))
    print("\n")
    if isinstance(command, click.Group):
        for name in command.list_commands(ctx):
            print_help(command.get_command(ctx, name), [*path, name], ctx)


print_help(cli, ["wetterdienst"])
```
