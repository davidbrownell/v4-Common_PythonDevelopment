# ----------------------------------------------------------------------
# |
# |  PyCoverageTestExecutor.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 15:58:28
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Extracts code coverage information using coverage."""

import datetime
import os
import re
import shlex
import sys
import textwrap
import time

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import EnsureValid, overridemethod

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.TesterPlugins.TestExecutorImpl import CoverageResult, ExecuteResult, TestExecutorImpl
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
sys.path.insert(0, str(Path(EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION"))) / "Scripts" / "Tester" / "Plugins" / "TestExecutors"))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0])
    from StandardTestExecutor import TestExecutor as StandardTestExecutor  # type: ignore  # pylint: disable=import-error


# ----------------------------------------------------------------------
class TestExecutor(TestExecutorImpl):
    """\
    Extracts code coverage information from python files. Coverage includes and excludes are
    extracted from optional comments embedded in the source.

    Available comments are:

        # code_coverage: disable

        # code_coverage: include = <Relative or full path to Python File #1>
        # code_coverage: include = <Relative or full path to Python File #2>
        # ...
        # code_coverage: include = <Relative or full path to Python File #N>

        # code_coverage: exclude = <Relative or full path to Python File #1>
        # code_coverage: exclude = <Relative or full path to Python File #2>
        # ...
        # code_coverage: exclude = <Relative or full path to Python File #N>

    Note that in no comment values are extracted from the source, the code will make a best-
    guess to find the production code based on the compiler being used.
    """

    # ----------------------------------------------------------------------
    def __init__(self):
        super(TestExecutor, self).__init__(
            "PyCoverage",
            "Extracts code coverage information for Python source code using coverage.py.",
            is_code_coverage_executor=True,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def GetCustomCommandLineArgs(self) -> TyperEx.TypeDefinitionsType:
        # No custom argument support
        return {}

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupportedCompiler(
        self,
        compiler: CompilerImpl,
    ) -> bool:
        # Use this file to determine if the compiler supports python files
        return compiler.IsSupported(Path(__file__))

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupportedTestItem(
        self,
        item: Path,
    ) -> bool:
        return item.suffix == ".py"

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,
        compiler: CompilerImpl,
        context: Dict[str, Any],
        command_line: str,
        on_progress: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
        includes: Optional[List[str]]=None,
        excludes: Optional[List[str]]=None,
    ) -> Tuple[ExecuteResult, str]:
        includes = includes or []
        excludes = excludes or []

        # Get the name of the python file to execute
        args = shlex.split(command_line)

        filename: Optional[Path] = next((Path(arg) for arg in args if os.path.isfile(arg)), None)

        assert filename is not None, args

        # Attempt to extract include and exclude information from the source
        disable_code_coverage = False

        if not disable_code_coverage and not includes and not excludes:
            regex = re.compile(
                r"""(?#
                Header                      )^.*?(?#
                Label                       )code_coverage\s*:\s*(?#
                Action                      )(?P<action>\S+)(?#
                +Optional                   )(?:(?#
                    Assignment              )\s*=\s*(?#
                    +Quote                  )(?P<quote>")?(?#
                    Name                    )(?P<name>.+?)(?#
                    -Quote                  )(?P=quote)?(?#
                -Optional                   ))?(?#
                Suffix                      )\s*$(?#
                )""",
            )

            for index, line in enumerate(filename.open().readlines()):
                match = regex.match(line)
                if not match:
                    continue

                action = match.group("action").lower()

                if action == "disable":
                    disable_code_coverage = True

                elif action in ["include", "exclude"]:
                    referenced_filename = (filename.parent / match.group("name")).resolve()

                    if not referenced_filename.is_file():
                        raise Exception(
                            "'{}', referenced on line {}, is not a valid file.\n".format(
                                referenced_filename,
                                index + 1,
                            ),
                        )

                    if action == "include":
                        includes.append(str(referenced_filename))
                    elif action == "exclude":
                        excludes.append(str(referenced_filename))
                    else:
                        assert False, action  # pragma: no cover

                else:
                    raise Exception("'{}', on line {}, is not a supported action.".format(action, index + 1))

        if disable_code_coverage:
            return StandardTestExecutor().Execute(
                dm,
                compiler,
                context,
                command_line,
                on_progress,
                includes,
                excludes,
            )

        # Attempt to determine include and exclude information based on the original filename
        if not includes and not excludes:
            sut_filename = compiler.TestItemToName(filename)
            if sut_filename is not None:
                # Get the relative module name for this file
                path_parts: List[str] = [sut_filename.name, ]

                for parent in sut_filename.parents:
                    if not (parent / "__init__.py").is_file():
                        break

                    path_parts.append(parent.name)

                includes.append("*/{}".format("/".join(reversed(path_parts))))

        # Run the process and calculate code coverage
        if command_line.startswith("python"):
            temp_filename = CurrentShell.CreateTempFilename(".py")

            with temp_filename.open("w") as f:
                f.write(
                    textwrap.dedent(
                        """\
                        from coverage.cmdline import main

                        main()
                        """,
                    ),
                )

            coverage_command_line_template = 'python "{}" run{{include}}{{omit}} "{}"'.format(temp_filename, filename)
            cleanup_func = temp_filename.unlink
        else:
            coverage_command_line_template = 'coverage run{{include}}{{omit}} -m {}'.format(command_line)
            cleanup_func = lambda: None

        # Execute the test
        test_execution_time: Optional[datetime.timedelta] = None
        test_result: Optional[int] = None
        test_output: Optional[str] = None

        with ExitStack(cleanup_func):
            # Run the process
            test_start_time = time.time()

            test_command_line = coverage_command_line_template.format(
                include=' "--include={}"'.format(",".join(includes)) if includes else "",
                omit=' "--omit={}"'.format(",".join(excludes)) if excludes else "",
            )

            dm.WriteLine("Decorated Command Line: {}\n\n".format(test_command_line))

            result = SubprocessEx.Run(test_command_line)

            test_execution_time = datetime.timedelta(seconds=time.time() - test_start_time)
            test_result = result.returncode
            test_output = result.output

        assert test_execution_time is not None
        assert test_result is not None
        assert test_output is not None

        # Generate the coverage data
        coverage_start_time = time.time()

        coverage_data_filename = Path(context["output_dir"]) / "coverage.xml"

        coverage_command_line = 'coverage xml -o "{}"'.format(coverage_data_filename)

        result = SubprocessEx.Run(coverage_command_line)

        coverage_execution_time = datetime.timedelta(seconds=time.time() - coverage_start_time)

        if not coverage_data_filename.is_file() and result.returncode == 0:
            result.returncode = -1

        test_output += "\n\n{}".format(result.output)

        if result.returncode != 0:
            coverage_result = CoverageResult(
                result.returncode,
                coverage_execution_time,
                "Coverage generation failed ({})".format(result.returncode),
                coverage_data_filename if coverage_data_filename.is_file() else None,
                coverage_percentage=None,
                coverage_percentages=None,
            )
        else:
            # Crack the coverage filename to get the percentage
            with coverage_data_filename.open() as f:
                root = ET.fromstring(f.read())

            coverage_percentages = {}

            for package in root.findall("packages/package"):
                for class_ in package.findall("classes/class"):
                    coverage_percentages[class_.attrib["filename"]] = float(class_.attrib["line-rate"])

            coverage_percentage = float(root.attrib["line-rate"])

            coverage_result = CoverageResult(
                result.returncode,
                coverage_execution_time,
                "Coverage: {}".format(coverage_percentage),
                coverage_data_filename,
                coverage_percentage,
                coverage_percentages or None,
            )

        return (
            ExecuteResult(
                test_result,
                test_execution_time,
                "Test {}".format(
                    "failed" if test_result < 0 else "has warnings" if test_result > 0 else "passed",
                ),
                coverage_result,
            ),
            test_output,
        )
