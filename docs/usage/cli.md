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
`--plausibility-consistency`, `--plausibility-floor` and `--plausibility-limits`, which take `hard` (null the value, keep the number as
`rejected:<check>,raw:<number>` in `quality_flags`) or `soft` (keep the value, flag it `suspect:<check>`), and
`WD_TS_PLAUSIBILITY__<CHECK>` sets one for a host. One not given keeps the host's mode, or its default (`stuck` is soft,
the others hard). `--plausibility soft` (or `hard`) sets all of them at once, and a check given beside it wins whatever the
order: `--plausibility soft --plausibility-range hard`; `WD_TS_PLAUSIBILITY=soft` does it for a host. A forecast network (`dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`: `kind` `forecast`) is judged soft in every check but `floor`, whatever is given: `hard` there is still flagged `suspect:<check>`, never nulled. See [plausibility checks](../data/plausibility.md).

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
network is soft in any case. `WD_TS_LIMITS` (JSON) sets them for a host, and a name given on the command line replaces
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

## Exit codes

What the command line promises across releases, its options and exit codes among it, is on the
[Compatibility](compatibility.md#command-line) page.

The exit code of a command is part of its contract, for the script, the scheduler and the CI job that branch on
it: it is `0`, `1` or `2`, and no command has another. A test holds every explicit exit and every error the
command line raises to these three, and each failure of the library to the status the REST API answers it with.

| Code | Meaning | REST | For instance |
| --- | --- | --- | --- |
| `0` | an answer, empty or not | 200 | the values; a window without readings, a name nothing is called or an id the network has no station for (the sentence is on stderr, and a `--target` is left as it is); `--help`, `--version` |
| `1` | a failure that is not the request's to rephrase | 5xx | a provider that failed or cannot be reached (`DownloadError`, `NoInternetError`), a credential or an extra the machine lacks, a malformed `WD_*` setting, a `--target` that cannot be written, a defect, Ctrl-C |
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
