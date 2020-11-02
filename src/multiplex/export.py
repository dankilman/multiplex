import json
import os
import string
from datetime import datetime

import aiofiles
from multiplex.ansi import C
from multiplex.iterator import Descriptor


class Export:
    def __init__(self, viewer):
        self.viewer = viewer

    async def save(self):
        viewer = self.viewer
        now = datetime.now()
        dir_name = f"output-{now.strftime('%Y-%m-%dT%H-%M-%S')}"
        output_dir = os.path.join(viewer.output_path, dir_name)
        os.makedirs(output_dir, exist_ok=True)
        valid_chars = string.ascii_letters + string.digits
        holders = viewer.holders
        zero_padding = 1 if len(holders) < 10 else 2
        metadata = {
            "view": {
                "maximized": viewer.maximized,
                "collapsed": viewer.collaped_all,
                "wrapped": viewer.wrapped_all,
            },
            "boxes": [],
        }
        for index, holder in enumerate(holders):
            initial_title = holder.iterator.title
            state = holder.state
            title = initial_title.to_string(no_style=True) if isinstance(initial_title, C) else str(initial_title)
            title = "".join(c for c in title if c in valid_chars).lower()
            file_name = f"{str(index + 1).zfill(zero_padding)}-{title}"
            async with aiofiles.open(os.path.join(output_dir, file_name), "w") as f:
                await f.write(holder.buffer.raw_buffer.getvalue())
            metadata["boxes"].append(
                {
                    "title": initial_title.to_dict() if isinstance(initial_title, C) else initial_title,
                    "box_height": state.box_height,
                    "collapsed": state.collapsed,
                    "wrap": state.wrap,
                    "filename": file_name,
                }
            )
        async with aiofiles.open(os.path.join(output_dir, "metadata.json"), "w") as f:
            await f.write(json.dumps(metadata, indent=2))
        viewer.output_saved = True
        viewer.events.send_output_saved()

    async def load(self, export_dir):
        viewer = self.viewer
        async with aiofiles.open(os.path.join(export_dir, "metadata.json")) as f:
            metadata = json.loads(await f.read())
        viewer.initial_add(
            [
                Descriptor(
                    obj=f"file://{export_dir}/{box['filename']}",
                    title=C.from_dict(box["title"]) if isinstance(box["title"], dict) else box["title"],
                    box_height=box["box_height"],
                    collapsed=box["collapsed"],
                    wrap=box["wrap"],
                )
                for box in metadata["boxes"]
            ]
        )
        view = metadata["view"]
        viewer.maximized = view["maximized"]
        viewer.collaped_all = view["collapsed"]
        viewer.wrapped_all = view["wrapped"]
