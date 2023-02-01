# ----------------------------------------------------------------------
# |
# |  BuildExeBuildInfo.py
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
"""Contains the BuildExeBuildInfo object"""

import os
import shutil

from enum import auto, Enum
from pathlib import Path
from typing import Callable, List, Optional, Pattern, TextIO, Tuple, Union

from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.BuildImpl import BuildInfoBase
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class BuildExeBuildInfo(BuildInfoBase):
    """Base class that can be used when building via 'setup.py build_exe'"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        build_name: str,
        working_dir: Path,
        required_development_configurations: Optional[list[Pattern]],
        *,
        disable_if_dependency_environment: bool,
    ):
        if not working_dir.is_dir():
            raise ValueError("'{}' is not a valid directory.".format(working_dir))

        setup_filename = working_dir / "setup.py"
        if not setup_filename.is_file():
            raise ValueError("'{}' must exist.".format(setup_filename))

        super(BuildExeBuildInfo, self).__init__(
            name=build_name,
            requires_output_dir=True,
            required_development_configurations=required_development_configurations,
            disable_if_dependency_environment=disable_if_dependency_environment,
        )

        self._working_dir                   = working_dir
        self._setup_filename                = setup_filename

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Path,
        output_stream: TextIO,
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
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
    @overridemethod
    def GetCustomBuildArgs(self) -> TyperEx.TypeDefinitionsType:
        """Return argument descriptions for any custom args that can be passed to the Build func on the command line"""

        # No custom args by default
        return {}

    # ----------------------------------------------------------------------
    @overridemethod
    def GetNumBuildSteps(
        self,
        configuration: Optional[str],  # pylint: disable=unused-argument
    ) -> int:
        return len(self.__class__._BuildSteps)  # pylint: disable=protected-access

    # ----------------------------------------------------------------------
    @overridemethod
    def Build(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Path,
        output_stream: TextIO,
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
        force: bool=False,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        with DoneManager.Create(
            output_stream,
            "Building '{}'...".format(output_dir),
            output_flags=DoneManagerFlags.Create(verbose=is_verbose, debug=is_debug),
        ) as dm:
            build_dir = self._working_dir / "build"

            if force:
                PathEx.RemoveTree(build_dir)

            with dm.Nested(
                "Building...",
                suffix="\n" if dm.is_verbose else "",
            ) as build_dm:
                on_progress_update(self.__class__._BuildSteps.Build.value, "Building...")  # pylint: disable=protected-access

                command_line = 'python setup.py build_exe'

                build_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

                result = SubprocessEx.Run(
                    command_line,
                    cwd=self._working_dir,
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
                on_progress_update(self.__class__._BuildSteps.Prune.value, "Pruning...")  # pylint: disable=protected-access

                directories: List[Path] = []

                for root, _, _ in os.walk(build_dir):
                    directories.append(Path(root))

                for directory in reversed(directories):
                    if not any(item for item in directory.iterdir()):
                        with prune_dm.VerboseNested("Removing '{}'...".format(directory)):
                            PathEx.RemoveTree(directory)

                if prune_dm.result != 0:
                    return prune_dm.result

            with dm.Nested("Moving content...") as move_dm:
                on_progress_update(self.__class__._BuildSteps.Move.value, "Moving...")  # pylint: disable=protected-access

                build_children: List[Path] = list(build_dir.iterdir())

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

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    class _BuildSteps(Enum):
        Build                               = 0
        Prune                               = auto()
        Move                                = auto()
