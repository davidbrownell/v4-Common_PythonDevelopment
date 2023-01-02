# ----------------------------------------------------------------------
# |
# |  InitializePythonPackage.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-29 14:17:27
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Initializes a python package within a repository."""

import os
import sys
import textwrap

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, cast, Optional

import typer

from semantic_version import Version as SemVer
from typer.core import TyperGroup

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import RegularExpression
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import Types


# ----------------------------------------------------------------------
sys.path.insert(0, Types.EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION")))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0]), sys.path[0]

    from RepositoryBootstrap import Constants as RepositoryBootstrapConstants  # type: ignore  # pylint: disable=import-error


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Configuration(object):
    repo_root: Path

    library_name: str
    library_version: SemVer
    library_description: str


# ----------------------------------------------------------------------
def _ValidateRepoRoot(
    value: Path,
) -> Path:
    if not (value / RepositoryBootstrapConstants.REPOSITORY_ID_FILENAME).is_file():
        raise typer.BadParameter(
            "'{}' is not a repository root ('{}' does not exist).".format(value, RepositoryBootstrapConstants.REPOSITORY_ID_FILENAME),
        )

    return value


# ----------------------------------------------------------------------
@app.command("EntryPoint")
def EntryPoint(
    repo_root: Path=typer.Option(Path.cwd(), "--repo-root", callback=_ValidateRepoRoot, help="Root of the repository that will contain the new package."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
) -> None:
    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        # Get the friendly name
        with (repo_root / RepositoryBootstrapConstants.REPOSITORY_ID_FILENAME).open() as f:
            content = f.read()

        match = RegularExpression.TemplateStringToRegex(RepositoryBootstrapConstants.REPOSITORY_ID_CONTENT_TEMPLATE).match(content)
        if not match:
            raise Exception("'{}' does not appear to be valid.".format(RepositoryBootstrapConstants.REPOSITORY_ID_FILENAME))

        friendly_name: Optional[str] = match.group("name")

        # See if the library name already exists
        if _GetLibraryDir(repo_root, cast(str, friendly_name)).is_dir():
            friendly_name = None

        # ----------------------------------------------------------------------
        def IsValidName(
            value: str,
        ) -> bool:
            return not _GetLibraryDir(repo_root, value).is_dir()

        # ----------------------------------------------------------------------
        def IsValidVersion(
            value: str,
        ) -> bool:
            try:
                SemVer.coerce(value)
                return True
            except:  # pylint: disable=bare-except
                return False

        # ----------------------------------------------------------------------

        library_name = _Prompt("Library name: ", friendly_name, IsValidName)
        library_version = _Prompt("Library version: ", "0.0.1", IsValidVersion)
        library_description = _Prompt("Library description: ", "Python library for '{}'.".format(library_name))

        output_dir = Execute(
            Configuration(
                repo_root,
                library_name,
                SemVer.coerce(library_version),
                library_description,
            ),
        )

        dm.WriteLine(
            textwrap.dedent(
                """\
                A python package has been initialized at '{}'.

                Consider adding the following to `{}`:

                    {}/src/{}.egg-info/*

                """,
            ).format(
                output_dir,
                repo_root / ".gitignore",
                Path(*output_dir.parts[len(repo_root.parts):]).as_posix(),
                library_name,
            ),
        )


# ----------------------------------------------------------------------
def Execute(
    config: Configuration,
) -> Path:
    output_dir = config.repo_root / RepositoryBootstrapConstants.LIBRARIES_SUBDIR / "Python" / config.library_name

    output_dir.mkdir(parents=True, exist_ok=True)

    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    code_dir = src_dir / config.library_name
    code_dir.mkdir(parents=True, exist_ok=True)

    with (code_dir / "__init__.py").open("w") as f:
        # Blank file
        pass

    with (output_dir / "pyproject.toml").open("w") as f:
        f.write(
            textwrap.dedent(
                """\
                [build-system]
                requires = ["setuptools>=63.0"]
                build-backend = "setuptools.build_meta"

                [project]
                name = "{name}"
                version = "{version}"
                description = "{description}"
                """,
            ).format(
                name=config.library_name,
                version=config.library_version,
                description=config.library_description,
            ),
        )

    return output_dir


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _Prompt(
    prompt: str,
    default_value: Optional[str]=None,
    is_valid_func: Optional[Callable[[str], bool]]=None,
) -> str:
    if default_value is not None:
        prompt += "[{}] ".format(default_value)

    while True:
        result = input(prompt).strip()
        if not result and default_value is not None:
            result = default_value

        if result and (not is_valid_func or is_valid_func(result)):
            return result


# ----------------------------------------------------------------------
def _GetLibraryDir(
    repo_root: Path,
    library_name: str,
) -> Path:
    return repo_root / RepositoryBootstrapConstants.LIBRARIES_SUBDIR / "Python" / library_name


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
