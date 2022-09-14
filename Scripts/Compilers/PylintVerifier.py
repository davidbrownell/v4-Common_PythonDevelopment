# ----------------------------------------------------------------------
# |
# |  PyLintVerifier.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 10:32:44
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Verifies Python source code using Pylint."""

import re
import textwrap

from enum import auto, Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Optional, Pattern, Tuple

import inflect as inflect_mod
import typer

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx

from Common_FoundationEx.CompilerImpl.VerifierBase import CreateVerifyCommandLineFunc, IndividualInputProcessingMixin, InputType, InvokeReason, VerifierBase
from Common_FoundationEx.CompilerImpl.InvocationMixins.IInvocation import IInvocation
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()

app                                         = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class Verifier(VerifierBase, IInvocation):
    """Verifies Python source code using Pylint"""

    # ----------------------------------------------------------------------
    # |  Public Types
    DEFAULT_PASSING_SCORE                   = 9.0

    # Optional
    PASSING_SCORE_ATTRIBUTE_NAME            = "passing_score"

    # Generated
    EXPLICIT_PASSING_SCORE_ATTRIBUTE_NAME   = "explicit_passing_score"

    # ----------------------------------------------------------------------
    class Steps(Enum):
        CalculatingConfiguration            = 0
        RunningPylint                       = auto()
        ExtractingScore                     = auto()

    # ----------------------------------------------------------------------
    # |  Public Methods
    def __init__(
        self,
        *,
        execute_converted_sut_files: bool=True,
    ):
        super(Verifier, self).__init__(
            "Pylint",
            "Statically analyzes Python source code using Pylint.",
            InputType.Files,
            execute_in_parallel=True,
        )

        self.execute_converted_sut_files    = execute_converted_sut_files

    # ----------------------------------------------------------------------
    @classmethod
    def GetCustomArgs(cls) -> TyperEx.TypeDefinitionsType:
        return {
            cls.PASSING_SCORE_ATTRIBUTE_NAME: (float, dict(min=0.0, max=10.0)),
        }

    # ----------------------------------------------------------------------
    def IsSupported(  # pylint: disable=arguments-renamed
        self,
        filename: Path,
    ) -> bool:
        return filename.suffix == ".py" and super(Verifier, self).IsSupported(filename)

    # ----------------------------------------------------------------------
    def IsTestItem(
        self,
        item: Path,
    ) -> bool:
        if item.name == "__init__.py":
            return False

        return super(Verifier, self).IsTestItem(item)

    # ----------------------------------------------------------------------
    def ItemToTestName(
        self,
        item: Path,
        test_type_name: str,
    ) -> Optional[Path]:
        if item.stem.lower().endswith("impl"):
            return None

        if item.name == "__init__.py" and item.stat().st_size == 0:
            return None

        if item.name == "__main__.py":
            return None

        if self.IsTestItem(item):
            return item

        return item.parent / "{}_{}{}".format(
            item.stem,
            inflect.singular_noun(test_type_name) or test_type_name,
            item.suffix,
        )

    # ----------------------------------------------------------------------
    _TestItemToName_regex: Optional[Pattern]            = None

    @classmethod
    def TestItemToName(
        cls,
        item: Path,
    ) -> Optional[Path]:
        if cls._TestItemToName_regex is None:
            cls._TestItemToName_regex = re.compile(
                textwrap.dedent(
                    r"""(?#
                    Start of content        )^(?#
                    Name                    )(?P<name>.+)_(?#
                    Test Type               )(?P<test_type>[^_\.]+Test)(?#
                    Extension               )(?P<ext>\..+)(?#
                    End of content          )$(?#
                    )""",
                ),
            )

        match = cls._TestItemToName_regex.match(item.name)
        if match is None:
            return None

        name = match.group("name")
        test_type = match.group("test_type")
        ext = match.group("ext")

        item = item.resolve()

        new_parent = item.parent

        if new_parent.name == inflect.plural(test_type):
            new_parent = new_parent.parent

        filename = new_parent / "{}{}".format(name, ext)
        if filename.is_file():
            return filename

        # Try a module name
        filename = filename.parent / "__init__.py"
        if filename.is_file() and filename.stat().st_size != 0:
            return filename

        return None

    # ----------------------------------------------------------------------
    @staticmethod
    def IsSupportedTestItem(
        item: Path,
    ) -> bool:
        if item.name in ["__init__.py", "__main__.py", "Build.py"]:
            return False

        if item.stem.lower().endswith("impl"):
            return False

        return True

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _EnumerateOptionalMetadata(cls) -> Generator[Tuple[str, Any], None, None]:
        yield cls.PASSING_SCORE_ATTRIBUTE_NAME, None
        yield from super(Verifier, cls)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @classmethod
    def _CreateContext(
        cls,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        if metadata[cls.PASSING_SCORE_ATTRIBUTE_NAME] is None:
            metadata[cls.PASSING_SCORE_ATTRIBUTE_NAME] = cls.DEFAULT_PASSING_SCORE
            metadata[cls.EXPLICIT_PASSING_SCORE_ATTRIBUTE_NAME] = False
        else:
            metadata[cls.EXPLICIT_PASSING_SCORE_ATTRIBUTE_NAME] = False

        return super(Verifier, cls)._CreateContext(dm, metadata)

    # ----------------------------------------------------------------------
    @classmethod
    def _GetNumStepsImpl(
        cls,
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> int:
        return len(cls.Steps)

    # ----------------------------------------------------------------------
    def _InvokeImpl(
        self,
        invoke_reason: InvokeReason,  # pylint: disable=unused-argument
        dm: DoneManager,
        context: Dict[str, Any],
        on_progress: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> Optional[str]:
        filename = context[IndividualInputProcessingMixin.ATTRIBUTE_NAME]

        # If the file is being invoked as a test file, measure the file that is the
        # system under test rather than the test file itself.

        potential_sut_filename = self.TestItemToName(filename)
        if potential_sut_filename is not None:
            dm.WriteInfo(
                "The test item '{}' was converted to '{}'.\n".format(
                    filename,
                    potential_sut_filename,
                ),
            )

            if not self.execute_converted_sut_files:
                dm.WriteInfo("Converted test items will not be run.\n")
                return "Skipped (converted test item)"

            filename = potential_sut_filename

        if not filename.is_file():
            dm.WriteInfo("The file '{}' does not exist.\n".format(filename))
            return "Skipped (file does not exist)"

        if filename.name == "__init__.py" and filename.stat().st_size == 0:
            dm.WriteInfo("The empty file '{}' will not be processed.\n".format(filename))
            return "Skipped (__init__.py)"

        if self.IsTestItem(filename):
            dm.WriteInfo(
                "The test item '{}' will not be processed.\n".format(
                    filename,
                ),
            )

            return "Skipped (test item)"

        # Find the configuration value
        configuration_filename: Optional[Path] = None

        on_progress(self.__class__.Steps.CalculatingConfiguration.value, "Calculating configuration")
        with dm.Nested("Calculating configuration..."):
            for parent in filename.parents:
                for name in ["pylintrc", ".pylintrc"]:
                    potential_filename = parent / name

                    if potential_filename.exists():
                        configuration_filename = potential_filename
                        break

                if configuration_filename is not None:
                    break

        # Execute
        output: Optional[str] = None

        on_progress(self.__class__.Steps.RunningPylint.value, "Running pylint")
        with dm.Nested(
            "Running pylint...",
            suffix="\n",
        ) as execute_dm:

            command_line = 'python -m pylint --persistent n {} "{}"'.format(
                '--rcfile "{}"'.format(configuration_filename) if configuration_filename is not None else "",
                filename,
            )

            execute_dm.WriteVerbose("\nCommand Line: {}\n\n".format(command_line))

            # TODO: Eventually, this should stream
            result = SubprocessEx.Run(command_line)

            # Pylint returns warnings in some scenarios. Unfortunately, the means that we have to
            # ignore the return code generated by the process.
            #
            # execute_dm.result = result.returncode

            output = result.output

            with execute_dm.YieldStream() as stream:
                stream.write(output)

        assert output is not None

        score: Optional[float] = None

        on_progress(self.__class__.Steps.ExtractingScore.value, "Extracting score")
        with dm.Nested("Extracting score...") as extract_dm:
            match = re.search(
                r"Your code has been rated at (?P<score>[-\d\.]+)/(?P<max>[\d\.]+)",
                output,
                re.MULTILINE,
            )

            if not match:
                dm.WriteError("The pylint output did not contain the expected content.\n")
                return

            score = float(match.group("score"))
            max_score = float(match.group("max"))
            assert max_score != 0.0
            assert score <= max_score, (score, max_score)

            passing_score = context[self.__class__.PASSING_SCORE_ATTRIBUTE_NAME]

            extract_dm.WriteInfo(
                textwrap.dedent(
                    """\

                    Score:                  {score} (out of {max_score})
                    Passing Score:          {passing_score}{explicit}

                    """,
                ).format(
                    score=score,
                    max_score=max_score,
                    passing_score=passing_score,
                    explicit=" (explicitly provided)" if context[self.__class__.EXPLICIT_PASSING_SCORE_ATTRIBUTE_NAME] else "",
                ),
            )

            if passing_score is not None and score < passing_score:
                extract_dm.result = -1

                return "{} < {}".format(score, passing_score)

            return "{} >= {}".format(score, passing_score)


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
Verify                                      = CreateVerifyCommandLineFunc(
    app,
    Verifier(
        # When running this verifier in isolation, we don't want to execute converted files as they
        # are likely to be picked up by a recursive search for all python files (since the verifier
        # when run from the command line, will generally be invoked on a root directory).
        #
        # When running as a part of Tester, we do want to execute the converted files because Tester
        # is pointed to the test files and won't pick up the converted files. Tester opts in to this
        # behavior by setting this value to True.
        #
        execute_converted_sut_files=False,
    ),
)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
