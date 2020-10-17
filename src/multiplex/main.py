import asyncio
import os
import sys
import warnings

import click
from multiplex.ipc import get_env_socket_path, Client
from multiplex.multiplex import Multiplex

warnings.simplefilter("ignore")


async def ipc_mode(socket_path, process, title, box_height):
    client = Client(socket_path)
    first = process[0]
    if first == "@":
        title = title or " ".join(process[1:])
        await client.split(title, box_height)
    elif first == "@save":
        await client.save()
    elif first == ":":
        await client.quit()
    elif first in {"/", "+", "-"}:
        value = None if first == "/" else True if first == "-" else False
        await client.toggle_collapse(value)
    elif len(process) == 1:
        await client.add(first, title, box_height)
    else:
        await client.batch([client.add_request_body(p, box_height=box_height, title=None) for p in process])


def direct_mode(process, title, verbose, box_height, output_path):
    multiplex = Multiplex(verbose=verbose, box_height=box_height, output_path=output_path)
    for p in process:
        multiplex.add(p, title=title)
    multiplex.run()
    for iterator in multiplex.viewer.iterators:
        exit_code = iterator.metadata.get("exit_code")
        if exit_code:
            sys.exit(exit_code)


@click.command()
@click.argument("process", nargs=-1)
@click.option("-t", "--title")
@click.option("-b", "--box-height", type=int)
@click.option(
    "-o",
    "--output-path",
    help="Root directory to use when saving output",
    default=os.getcwd(),
    envvar="MULTIPLEX_OUTPUT_PATH",
)
@click.help_option("-h", "--help")
@click.version_option(None, "--version")
@click.option("-v", "--verbose", is_flag=True)
def main(process, title, verbose, box_height, output_path):
    if not process:
        raise click.ClickException("At least one command is required")
    if title and len(process) > 1:
        raise click.ClickException("title can only be used with 1 process")

    socket_path = get_env_socket_path()
    if socket_path:
        asyncio.run(
            ipc_mode(
                socket_path=socket_path,
                process=process,
                title=title,
                box_height=box_height,
            )
        )
    else:
        direct_mode(
            process=process,
            title=title,
            verbose=verbose,
            box_height=box_height,
            output_path=output_path,
        )
