import sys
import warnings

import click
from multiplex.multiplex import Multiplex

warnings.simplefilter("ignore")


@click.command()
@click.argument("process", nargs=-1)
@click.help_option("-h", "--help")
@click.version_option(None, "--version")
@click.option("-v", "--verbose", is_flag=True)
def main(process, verbose):
    if not process:
        raise click.ClickException("At least one command is required")
    multiplex = Multiplex(verbose=verbose)
    for p in process:
        multiplex.add(p)
    multiplex.run()
    for iterator in multiplex.iterators:
        exit_code = iterator.metadata.get("exit_code")
        if exit_code:
            sys.exit(exit_code)
