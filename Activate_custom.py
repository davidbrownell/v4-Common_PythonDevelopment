# ----------------------------------------------------------------------
# |
# |  Activate_custom.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-07 10:21:49
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
# pylint: disable=missing-module-docstring

import os

from pathlib import Path
from typing import List, Optional

from Common_Foundation.Shell import Commands                                # type: ignore  # pylint: disable=import-error,unused-import
from Common_Foundation.Streams.DoneManager import DoneManager               # type: ignore  # pylint: disable=import-error,unused-import

from RepositoryBootstrap import Configuration                               # type: ignore  # pylint: disable=import-error,unused-import
from RepositoryBootstrap import Constants                                   # type: ignore  # pylint: disable=import-error,unused-import
from RepositoryBootstrap import DataTypes                                   # type: ignore  # pylint: disable=import-error,unused-import
from RepositoryBootstrap.SetupAndActivate import DynamicPluginArchitecture  # type: ignore  # pylint: disable=import-error,unused-import


# ----------------------------------------------------------------------
# Note that it is safe to remove this function if it will never be used.
def GetCustomActions(                                                       # pylint: disable=too-many-arguments
    # Note that it is safe to remove any parameters that are not used
    dm: DoneManager,                                                        # pylint: disable=unused-argument
    repositories: List[DataTypes.ConfiguredRepoDataWithPath],               # pylint: disable=unused-argument
    generated_dir: Path,                                                    # pylint: disable=unused-argument
    configuration: Optional[str],                                           # pylint: disable=unused-argument
    version_specs: Configuration.VersionSpecs,                              # pylint: disable=unused-argument
    force: bool,                                                            # pylint: disable=unused-argument
    is_mixin_repo: bool,                                                    # pylint: disable=unused-argument
) -> List[Commands.Command]:
    """Returns a list of actions that should be invoked as part of the activation process."""

    commands: List[Commands.Command] = []

    root_dir = Path(__file__).parent
    assert root_dir.is_dir(), root_dir

    scripts_dir = root_dir / Constants.SCRIPTS_SUBDIR
    assert scripts_dir.is_dir(), scripts_dir

    with dm.VerboseNested(
        "\nActivating dynamic plugins from '{}'...".format(root_dir),
        suffix="\n" if dm.is_debug else "",
    ) as nested_dm:
        for env_name, subdir, name_suffixes in [
            ("DEVELOPMENT_ENVIRONMENT_COMPILERS", "Compilers", ["Compiler", "Verifier"]),
            ("DEVELOPMENT_ENVIRONMENT_TEST_EXECUTORS", os.path.join("TesterPlugins", "TestExecutors"), ["TestExecutor"]),
            ("DEVELOPMENT_ENVIRONMENT_TEST_PARSERS", os.path.join("TesterPlugins", "TestParsers"), ["TestParser"]),
        ]:
            commands += DynamicPluginArchitecture.CreateRegistrationCommands(
                nested_dm,
                env_name,
                scripts_dir / subdir,
                lambda fullpath: (
                    fullpath.suffix == ".py"
                    and any(fullpath.stem.endswith(name_suffix) for name_suffix in name_suffixes)  # pylint: disable=cell-var-from-loop
                ),
            )

    commands.append(
        Commands.Augment(
            "DEVELOPMENT_ENVIRONMENT_TESTER_CONFIGURATIONS",
            [
                # <configuration name>-<plugin type>-<value>[-pri=<priority>]
                "python-compiler-Pylint",
                "python-test_parser-Pytest",
                "python-coverage_executor-PyCoverage"
            ],
        ),
    )

    commands.append(
        Commands.Set(
            "DEVELOPMENT_ENVIRONMENT_PYTHON_DEVELOPMENT_ROOT",
            str(root_dir),
        ),
    )

    return commands


# ----------------------------------------------------------------------
# Note that it is safe to remove this function if it will never be used.
def GetCustomActionsEpilogue(                                               # pylint: disable=too-many-arguments
    # Note that it is safe to remove any parameters that are not used
    dm: DoneManager,                                                        # pylint: disable=unused-argument
    repositories: List[DataTypes.ConfiguredRepoDataWithPath],               # pylint: disable=unused-argument
    generated_dir: Path,                                                    # pylint: disable=unused-argument
    configuration: Optional[str],                                           # pylint: disable=unused-argument
    version_specs: Configuration.VersionSpecs,                              # pylint: disable=unused-argument
    force: bool,                                                            # pylint: disable=unused-argument
    is_mixin_repo: bool,                                                    # pylint: disable=unused-argument
) -> List[Commands.Command]:
    """\
    Returns a list of actions that should be invoked as part of the activation process. Note
    that this is called after `GetCustomActions` has been called for each repository in the dependency
    list.

    ********************************************************************************************
    Note that it is very rare to have the need to implement this method. In most cases, it is
    safe to delete the entire method. However, keeping the default implementation (that
    essentially does nothing) is not a problem.
    ********************************************************************************************
    """

    return []
