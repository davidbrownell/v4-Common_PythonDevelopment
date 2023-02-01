# ----------------------------------------------------------------------
# |
# |  BuildPythonExecutable.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-01-31 08:24:38
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality that helps when implementing a Build file that builds a python executable"""

import inspect
import os
import shutil

from enum import auto, Enum
from pathlib import Path
from typing import Callable, Optional, TextIO, Tuple, Union

from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import SubprocessEx


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class BuildSteps(Enum):
    Compile                             = 0
    Prune                               = auto()
    Move                                = auto()


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def Clean(
    output_dir: Path,
    output_stream: TextIO,
    *,
    is_verbose: bool,
    is_debug: bool,
) -> Union[
    int,                                    # Error code
    Tuple[
        int,                                # Error code
        str,                                # Short text that provides information about the result
    ],
]:
    with DoneManager.Create(
        output_stream,
        "Cleaning '{}'...".format(output_dir),
        output_flags=DoneManagerFlags.Create(verbose=is_verbose, debug=is_debug),
    ) as dm:
        if not output_dir.is_dir():
            dm.WriteInfo("The directory '{}' does not exist.\n".format(output_dir))
        else:
            PathEx.RemoveTree(output_dir)

    return 0


# ----------------------------------------------------------------------
def Build(
    output_dir: Path,
    output_stream: TextIO,
    on_progress_update: Callable[
        [
            int,                            # Step ID (zero-based)
            str,                            # Status info
        ],
        bool,                               # True to continue, False to terminate
    ],
    *,
    is_verbose: bool,
    is_debug: bool,
    force: bool=False,
    working_dir: Optional[Path]=None,
) -> Union[
    int,                                    # Error code
    Tuple[
        int,                                # Error code
        str,                                # Short text that provides information about the result
    ],
]:
    if working_dir is None:
        caller = inspect.getouterframes(inspect.currentframe(), 2)[1]
        working_dir = PathEx.EnsureDir(Path(caller.filename).parent)

    with DoneManager.Create(
        output_stream,
        "Building '{}'...".format(output_dir),
        output_flags=DoneManagerFlags.Create(verbose=is_verbose, debug=is_debug),
    ) as dm:
        build_dir = working_dir / "build"

        if force:
            PathEx.RemoveTree(build_dir)

        with dm.Nested(
            "Compiling...",
            suffix="\n" if dm.is_verbose else "",
        ) as build_dm:
            on_progress_update(BuildSteps.Compile.value, "Compiling...")

            command_line = 'python setup.py build_exe'

            build_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

            result = SubprocessEx.Run(
                command_line,
                cwd=working_dir,
                supports_colors=False,
            )

            build_dm.result = result.returncode

            if build_dm.result != 0:
                build_dm.WriteError(result.output)
                return build_dm.result

            with build_dm.YieldVerboseStream() as stream:
                stream.write(result.output)

        with dm.Nested(
            "Pruning...",
            suffix="\n" if dm.is_verbose else "",
        ) as prune_dm:
            on_progress_update(BuildSteps.Prune.value, "Pruning...")

            directories: list[Path] = []

            for root, _, _ in os.walk(build_dir):
                directories.append(Path(root))

            for directory in reversed(directories):
                if not any(item for item in directory.iterdir()):
                    with prune_dm.VerboseNested("Removing '{}'...".format(directory)):
                        PathEx.RemoveTree(directory)

            if prune_dm.result != 0:
                return prune_dm.result

        with dm.Nested("Moving content...") as move_dm:
            on_progress_update(BuildSteps.Move.value, "Moving...")  # pylint: disable=protected-access

            build_children: list[Path] = list(build_dir.iterdir())

            assert len(build_children) == 1

            content_dir = build_children[0]

            PathEx.RemoveTree(output_dir)
            output_dir.mkdir(parents=True)

            for child in content_dir.iterdir():
                shutil.move(child, output_dir)

            PathEx.RemoveTree(build_dir)

            if move_dm.result != 0:
                return move_dm.result

        return dm.result
