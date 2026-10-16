---
file_format: mystnb
kernelspec:
  name: python3
---

# Command Line Interface

Exit codes: `0` for an answer, empty or not -- a window without readings or a name nothing is called
exits 0 with the sentence on stderr, as the REST API answers such a request with a 200 and an empty
`values` or `stations` --, `1` for a failure, and `2` for a request that cannot be served as phrased. A list of
`--stations` ids leaves out an id the network has no station for and says so in a warning. A boolean
option is the same everywhere: bare, as `--pretty`, or as `--pretty=true` and `--pretty=false`. The command line
and the [REST API](restapi.md) render a result through the same function, so the same request gives the
same output, a `settings` block with `--with-metadata` included.

An option is spelled as the REST query parameter and the MCP argument of the same request, with hyphens
for underscores (`--name-threshold` is `name_threshold`), and a list is plural and comma-separated
(`--stations=01048,04411`). The names the options had before, `--convert_units`, `--station` for a list
and the like, fail with an error naming the new one. See [one vocabulary](restapi.md#one-vocabulary).

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
