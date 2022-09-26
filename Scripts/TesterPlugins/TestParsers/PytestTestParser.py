# ----------------------------------------------------------------------
# |
# |  PytestTestParser.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 22:24:32
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Parses content produced by Python's pytest library."""

import datetime
import re
import sys
import time

from pathlib import Path
from typing import Any, Callable, Dict, List

from Common_Foundation.Types import overridemethod

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.CompilerImpl.Mixins.InputProcessorMixins.IndividualInputProcessorMixin import IndividualInputProcessorMixin
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx.TesterPlugins.TestParserImpl import BenchmarkStat, SubtestResult, TestParserImpl, TestResult, Units
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class TestParser(TestParserImpl):
    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(self):
        super(TestParser, self).__init__("Pytest", "Parses Python pytest output.")

    # ----------------------------------------------------------------------
    @overridemethod
    def GetCustomCommandLineArgs(self) -> TyperEx.TypeDefinitionsType:
        return {}

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupportedCompiler(
        self,
        compiler: CompilerImpl,
    ) -> bool:
        # Use the file to determine if the compiler supports python files
        return compiler.IsSupported(Path(__file__))

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupportedTestItem(
        self,
        item: Path,
    ) -> bool:
        # Don't look for explicit pytest imports, as pytest doesn't require them.
        # Check to see that the file is a python file.
        return item.is_file() and item.suffix == ".py"

    # ----------------------------------------------------------------------
    @overridemethod
    def CreateInvokeCommandLine(
        self,
        compiler: CompilerImpl,
        context: Dict[str, Any],
        *,
        debug_on_error: bool=False,
    ) -> str:
        # Note that pytest MUST be invoked as 'pytest <args>' rather than 'python -m pytest <args>' to
        # work with PyCoverageTestExecutor.
        command_line_prefix = 'pytest --verbose -vv --capture=no'

        return '{} "{}"'.format(
            command_line_prefix,
            super(TestParser, self).CreateInvokeCommandLine(
                compiler,
                context,
                debug_on_error=debug_on_error,
            ),
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def Parse(
        self,
        compiler: CompilerImpl,             # pylint: disable=unused-argument
        compiler_context: Dict[str, Any],
        test_data: str,
        on_progress_func: Callable[         # pylint: disable=unused-argument
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> TestResult:
        start_time = time.time()

        filename = compiler_context[IndividualInputProcessorMixin.ATTRIBUTE_NAME]

        # Get the individual results
        individual_results: Dict[str, SubtestResult] = {}
        num_failures = 0

        for match in self.__class__._parse_individual_regex.finditer(test_data):  # pylint: disable=protected-access
            result = match.group("result")

            if result == "PASSED":
                result = 0
            elif result == "FAILED":
                result = -1
                num_failures += 1
            else:
                assert False, result  # pragma: no cover

            individual_results[match.group("test")] = SubtestResult(result, datetime.timedelta())

        benchmarks: List[BenchmarkStat] = []

        match = self.__class__._parse_benchmark_content_regex.search(test_data)  # pylint: disable=protected-access
        if match:
            # Get the pytest and benchmark versions
            pytest_version = self.__class__._pytest_version_regex.search(test_data)  # pylint: disable=protected-access
            assert pytest_version
            pytest_version = pytest_version.group("value")

            benchmark_version = self.__class__._benchmark_version_regex.search(test_data)  # pylint: disable=protected-access
            assert benchmark_version
            benchmark_version = benchmark_version.group("value")

            # Parse the match for individual benchmarks
            units = match.group("units")
            match = match.group("content")

            version_info = "{}.{}.{} / {} / {}".format(
                sys.version_info.major,
                sys.version_info.minor,
                sys.version_info.micro,
                pytest_version,
                benchmark_version,
            )

            for line_item in match.split("\n"):
                line_item = line_item.strip()

                match = self.__class__._parse_benchmark_line_item_regex.match(line_item)  # pylint: disable=protected-access
                assert match, line_item

                benchmarks.append(
                    BenchmarkStat(
                        match.group("name"),
                        filename,
                        1, # Line Number (we don't have a way to get the actual data (that I know of))
                        version_info,
                        float(match.group("min").replace(",", "")),
                        float(match.group("max").replace(",", "")),
                        float(match.group("mean").replace(",", "")),
                        float(match.group("std_dev").replace(",", "")),
                        int(match.group("rounds")),
                        Units(units),
                        int(match.group("iterations")),
                    ),
                )

        if not individual_results:
            result = -2
            short_desc = "Invalid test output"
        elif num_failures != 0:
            result = -1
            short_desc = "{} failed".format(inflect.no("test", num_failures))
        else:
            result = 0
            short_desc = "{} passed".format(inflect.no("test", len(individual_results)))

        return TestResult(
            result,
            datetime.timedelta(seconds=time.time() - start_time),
            short_desc,
            individual_results or None,
            {filename.name: benchmarks} if benchmarks else None,
        )

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    _parse_individual_regex                 = re.compile(
        r"""(?#
        Start of line                       )^(?#
        Filename                            )(?P<filename>.+\.py)(?#
        Sep                                 )::(?#
        Test                                )(?P<test>.+)(?#
        Result                              )\s+(?P<result>[A-Z]+)(?#
        End of line                         )$(?#
        )""",
        re.MULTILINE,
    )

    _pytest_version_regex                   = re.compile(r"(?P<value>pytest-\d+\.\d+\.\d+)")
    _benchmark_version_regex                = re.compile(r"(?P<value>benchmark-\d+\.\d+\.\d+)")

    _parse_benchmark_content_regex          = re.compile(
        r"""(?#
        Header Prefix                       )----+ benchmark: \d+ tests ----+\r?\n(?#
        Header
            Name                            )Name \(time in (?P<units>\S+)\)\s+(?#
            Min                             )Min\s+(?#
            Max                             )Max\s+(?#
            Mean                            )Mean\s+(?#
            StdDev                          )StdDev\s+(?#
            Median                          )Median\s+(?#
            InterQuartile Range             )IQR\s+(?#
            Outliers                        )Outliers\s+(?#
            Operations per second           )OPS \(Mops/s\)\s+(?#
            Rounds                          )Rounds\s+(?#
            Iterations                      )Iterations\r?\n(?#
        Header Suffix                       )----+\r?\n(?#
        Content                             )(?P<content>.+)\r?\n(?#
        Footer                              )----+\r?\n(?#
        )""",
        re.DOTALL | re.MULTILINE,
    )

    _parse_benchmark_line_item_regex        = re.compile(
        r"""(?#
        Name                                )(?P<name>\S+)\s+(?#
        Min                                 )(?P<min>{float_regex})(?: \((?P<min_dev>{float_regex})\))?\s+(?#
        Max                                 )(?P<max>{float_regex})(?: \((?P<max_dev>{float_regex})\))?\s+(?#
        Mean                                )(?P<mean>{float_regex})(?: \((?P<mean_dev>{float_regex})\))?\s+(?#
        StdDev                              )(?P<std_dev>{float_regex})(?: \((?P<std_dev_dev>{float_regex})\))?\s+(?#
        Median                              )(?P<median>{float_regex})(?: \((?P<median_dev>{float_regex})\))?\s+(?#
        IQR                                 )(?P<iqr>{float_regex})(?: \((?P<iqr_dev>{float_regex})\))?\s+(?#
        Outliers                            )(?P<outlier_first>\d+);(?P<outlier_second>\d+)\s+(?#
        OPS                                 )(?P<ops>{float_regex})(?: \((?P<ops_dev>{float_regex})\))?\s+(?#
        Rounds                              )(?P<rounds>\d+)\s+(?#
        Iterations                          )(?P<iterations>\d+)(?#
        )""".format(
            float_regex=r"[\d,]+\.\d+",
        ),
    )
