---
file_format: mystnb
kernelspec:
  name: python3
---

# Command Line Interface

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
