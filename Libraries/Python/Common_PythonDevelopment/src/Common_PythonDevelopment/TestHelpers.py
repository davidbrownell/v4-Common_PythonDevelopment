# ----------------------------------------------------------------------
# |
# |  TestHelpers.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-12-19 09:19:56
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Functionality that is helpful when writing automated tests"""

import inspect
import textwrap

from pathlib import Path
from typing import Callable, Optional


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
DEFAULT_SUFFIX                              = None
DEFAULT_SUBDIR                              = "Results"
DEFAULT_FILE_EXTENSION                      = ".txt"
DEFAULT_CALL_STACK_OFFSET                   = 0


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def ResultsFromFile(
    suffix: Optional[str]=DEFAULT_SUFFIX,
    subdir: str=DEFAULT_SUBDIR,
    file_extension: str=DEFAULT_FILE_EXTENSION,
    call_stack_offset: int=DEFAULT_CALL_STACK_OFFSET,
    decorate_test_name_func: Optional[Callable[[str], str]]=None,
    decorate_stem_func: Optional[Callable[[str], str]]=None,
) -> str:
    """\
    Returns results saved from a file, where the filename is dynamically created based on the
    name of the test calling this function.

    By default, returns should be stored in a directory relative to the test file:

        Results/<basename>.<test_name>.txt
        Results/<basename>.<classname>.<test_name>.txt

        Results/<basename>.<test_name><suffix>.txt
        Results/<basename>.<classname>.<test_name><suffix>.txt

    Examples:

        # In Test File named: MyTests.py

        def test_MyFunction():
            assert ResultsFromFile() == "foo"  # Results/MyTests.test_MyFunction.txt

        class MyClass(object):
            def test_MyMethod(self):
                assert ResultsFromFile() == "bar"  # Results/MyTests.MyClass.test_MyMethod.txt
    """

    fullpath = _GetResultsFilename(
        suffix,
        subdir,
        file_extension,
        call_stack_offset + 1,
        decorate_test_name_func,
        decorate_stem_func,
    )

    if not fullpath.is_file():
        return textwrap.dedent(
            """\
            ********************************************************************************
            ********************************************************************************
            ********************************************************************************

            WARNING:
                The filename does not exist:

                    {}

            ********************************************************************************
            ********************************************************************************
            ********************************************************************************
            """,
        ).format(fullpath)

    with fullpath.open() as f:
        return f.read()


# ----------------------------------------------------------------------
def CompareResultsFromFile(
    results: str,
    *,
    suffix: Optional[str]=DEFAULT_SUFFIX,
    subdir: str=DEFAULT_SUBDIR,
    file_extension: str=DEFAULT_FILE_EXTENSION,
    call_stack_offset: int=DEFAULT_CALL_STACK_OFFSET,
    decorate_test_name_func: Optional[Callable[[str], str]]=None,
    decorate_stem_func: Optional[Callable[[str], str]]=None,
    overwrite_content_with_current_results: bool=False,
) -> None:
    """\
    Compares the results provided with the results from a file on the filesystem (whose name is
    calculated dynamically based on the name of the test calling this function).

    To use this functionality with pytest, include the following statements BEFORE this file is
    imported:

        import pytest
        pytest.register_assert_rewrite("Common_PythonDevelopment.TestHelpers")

        from Common_PythonDevelopment.TestHelpers import CompareResultsFromFile

    """

    if overwrite_content_with_current_results:
        filename = _GetResultsFilename(
            suffix,
            subdir,
            file_extension,
            call_stack_offset + 1,
            decorate_test_name_func,
            decorate_stem_func,
        )

        print(
            textwrap.dedent(
                """\
                ********************************************************************************
                ********************************************************************************
                ********************************************************************************

                WARNING:
                    File contents are being overwritten for:

                        {}

                ********************************************************************************
                ********************************************************************************
                ********************************************************************************
                """,
            ).format(filename),
        )

        with filename.open("w") as f:
            f.write(results)

    assert results == ResultsFromFile(
        suffix,
        subdir,
        file_extension,
        call_stack_offset + 1,
        decorate_test_name_func,
        decorate_stem_func,
    )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _GetResultsFilename(
    suffix: Optional[str],
    subdir: str,
    file_extension: str,
    call_stack_offset: int,
    decorate_test_name_func: Optional[Callable[[str], str]],
    decorate_stem_func: Optional[Callable[[str], str]],
) -> Path:
    caller = inspect.getouterframes(inspect.currentframe(), 2)[1 + call_stack_offset]

    test_name = caller.function
    if decorate_test_name_func is not None:
        test_name = decorate_test_name_func(test_name)

    self_value = caller.frame.f_locals.get("self", None)
    if self_value is not None:
        test_name = "{}.{}".format(self_value.__class__.__name__, test_name)

    filename = Path(caller.filename)

    return filename.parent / subdir / "{}.{}{}{}".format(
        decorate_stem_func(filename.stem) if decorate_stem_func is not None else filename.stem,
        test_name,
        suffix or "",
        file_extension,
    )
