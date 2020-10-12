import sys
import warnings

import click
from multiplex.view_builder import ViewBuilder

warnings.simplefilter("ignore")


@click.command()
@click.argument("process", nargs=-1)
@click.help_option("-h", "--help")
@click.version_option(None, "--version")
@click.option("-v", "--verbose", is_flag=True)
def main(process, verbose):
    if not process:
        raise click.ClickException("At least one command is required")
    builder = ViewBuilder(verbose=verbose)
    for p in process:
        builder.add(p)
    viewer = builder.build()
    viewer.run()
    for iterator in builder.iterators:
        exit_code = iterator.metadata.get("exit_code")
        if exit_code:
            sys.exit(exit_code)
