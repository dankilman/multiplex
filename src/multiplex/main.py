import sys

import click
from multiplex import to_iterator, Viewer


@click.command()
@click.argument("process", nargs=-1)
@click.help_option("-h", "--help")
@click.version_option(None, "-v", "--version")
def main(process):
    if not process:
        raise click.ClickException("At least one command is required")
    iterators = []
    for p in process:
        iterators.append(to_iterator(p))
    viewer = Viewer(iterators)
    viewer.run()
    for iterator in iterators:
        exit_code = iterator.metadata.get("exit_code")
        if exit_code:
            sys.exit(exit_code)
