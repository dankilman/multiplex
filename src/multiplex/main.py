import asyncio
import os
import sys
from itertools import cycle

import click
from multiplex.exceptions import IPCException
from multiplex.ipc import Client, get_env_stream_id
from multiplex.iterator import MULTIPLEX_SOCKET_PATH
from multiplex.multiplex import Multiplex


async def ipc_mode(socket_path, process, title, box_height, wait, load):
    client = Client(socket_path)
    first = process[0] if not load else None
    env = os.environ.copy()
    cwd = os.getcwd()
    if load:
        await client.load(load)
    elif first == "@":
        stream_id = get_env_stream_id()
        title = title[0] or " ".join(process[1:])
        await client.split(title, box_height[0], stream_id)
    elif first == "@save":
        await client.save()
    elif first == ":":
        await client.quit()
    elif first in {"/", "+", "-"}:
        value = None if first == "/" else True if first == "-" else False
        await client.toggle_collapse(value)
    elif len(process) == 1:
        await client.add(first, title[0], box_height[0], wait[0], cwd, env)
    else:
        actions = []
        for p, t, h, w in zip(process, cycle(title), cycle(box_height), cycle(wait)):
            actions.append(client.add_request_body(p, title=t, box_height=h, wait=w, cwd=cwd, env=env))
        await client.batch(actions)


def direct_mode(process, title, verbose, box_height, output_path, load, socket_path, buffer_lines):
    multiplex = Multiplex(
        verbose=verbose,
        box_height=box_height[0],
        output_path=output_path,
        socket_path=socket_path,
        buffer_lines=buffer_lines,
    )
    for p, t, h in zip(process, cycle(title), cycle(box_height)):
        multiplex.add(p, title=t, box_height=h)
    multiplex.run(load)
    for iterator in multiplex.viewer.iterators:
        exit_code = iterator.metadata.get("exit_code")
        if exit_code:
            sys.exit(exit_code)


def validate(box_height, process, socket_path, title, wait, load):
    if load:
        if not os.path.isdir(load):
            raise click.ClickException(f"No such dir: {load}")
        if not os.path.exists(os.path.join(load, "metadata.json")):
            raise click.ClickException(f"Invalid directory: {load}")
        return
    if not process:
        raise click.ClickException("At least one command is required")
    if title and len(title) != len(process):
        raise click.ClickException(
            f"Each process should have a title, but {len(title)} titles and {len(process)} processes were supplied"
        )
    if wait and not socket_path:
        raise click.ClickException(f"wait can only be used when running inside a process started by multiplex")
    if len(wait) > 1 and len(wait) != len(process):
        raise click.ClickException(
            f"wait should be supplied either once to apply to all boxes or once for each process, "
            f"but {len(wait)} wait's and {len(process)} processes were supplied"
        )
    if len(box_height) > 1 and len(box_height) != len(process):
        raise click.ClickException(
            f"Box height should be supplied either once to apply to all boxes or once for each process, "
            f"but {len(box_height)} box heights and {len(process)} processes were supplied"
        )


@click.command()
@click.argument("process", nargs=-1)
@click.option("-t", "--title", multiple=True)
@click.option("-b", "--box-height", type=int, multiple=True)
@click.option("--wait/--no-wait", "-w/-W", multiple=True)
@click.option("-l", "--load")
@click.option(
    "--buffer-lines",
    type=int,
    envvar="MULTIPLEX_BUFFER_LINES",
    help="By default, buffer length is unbounded. Use this to have a maximum number of lines for each " "buffer.",
)
@click.option(
    "-o",
    "--output-path",
    help="Root directory to use when saving output",
    default=os.getcwd(),
    envvar="MULTIPLEX_OUTPUT_PATH",
)
@click.option(
    "-s",
    "--socket-path",
    envvar=MULTIPLEX_SOCKET_PATH,
)
@click.option(
    "--server",
    is_flag=True,
    help="This should only be used when socket path is provided explicity to instantiate the server. "
    "Otherwise, the command is assumed to be executed in IPC mode",
)
@click.help_option("-h", "--help")
@click.version_option(None, "--version")
@click.option("-v", "--verbose", is_flag=True)
def main(process, title, verbose, box_height, output_path, wait, load, socket_path, buffer_lines, server):
    validate(
        box_height=box_height,
        process=process,
        socket_path=socket_path,
        title=title,
        wait=wait,
        load=load,
    )

    title = title or [None]
    box_height = box_height or [None]
    wait = wait or [True]

    if socket_path and not server:
        try:
            asyncio.run(
                ipc_mode(
                    socket_path=socket_path,
                    process=process,
                    title=title,
                    box_height=box_height,
                    wait=wait,
                    load=load,
                )
            )
        except IPCException as e:
            raise click.ClickException(str(e))
    else:
        direct_mode(
            process=process,
            title=title,
            verbose=verbose,
            box_height=box_height,
            output_path=output_path,
            load=load,
            socket_path=socket_path,
            buffer_lines=buffer_lines,
        )
