# ----------------------------------------------------------------------
# |
# |  PathMock_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-21 14:09:48
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Unit tests for PathMock.py"""

from pathlib import Path
from typing import List
from unittest import mock

from Common_PythonDevelopment.MockHelpers.PathMock import *


# ----------------------------------------------------------------------
def test_IndependentAttributes():
    isdir_mock = mock.Mock()
    isfile_mock = mock.Mock()

    p = CreatePathMock(
        Path("one"),
        is_dir=isdir_mock,
        is_file=isfile_mock,
    )

    p.is_dir()

    assert isdir_mock.call_count == 1
    assert isfile_mock.call_count == 0

    isdir_mock.reset_mock()
    isfile_mock.reset_mock()

    p.is_file()

    assert isdir_mock.call_count == 0
    assert isfile_mock.call_count == 1

    isdir_mock.reset_mock()
    isfile_mock.reset_mock()

    p.is_file()
    p.is_dir()
    p.is_file()

    assert isdir_mock.call_count == 1
    assert isfile_mock.call_count == 2


# ----------------------------------------------------------------------
def test_Children():
    exists_mock = mock.Mock()

    parent = CreatePathMock(
        Path("does_not_exist"),
        exists=exists_mock,
    )

    child = parent / "child"
    grandchild = child / "grandchild"

    assert parent.is_dir() is False
    assert parent.is_file() is False
    assert exists_mock.call_count == 0

    assert child.is_dir() is False
    assert child.is_file() is False
    assert exists_mock.call_count == 0

    parent.exists()
    assert exists_mock.call_count == 1

    child.exists()
    assert exists_mock.call_count == 2

    parent.exists()
    assert exists_mock.call_count == 3

    grandchild.exists()
    assert exists_mock.call_count == 4


# ----------------------------------------------------------------------
def test_Func():
    values: List[str] = []

    # ----------------------------------------------------------------------
    def Exists(
        value: Path,
    ) -> bool:
        values.append(value.as_posix())
        return value == Path("root/child")

    # ----------------------------------------------------------------------

    parent = CreatePathMock(
        Path("root"),
        exists=Exists,
    )

    child = parent / "child"
    grandchild = child / "grandchild"

    assert child.exists() is True
    assert grandchild.exists() is False
    assert parent.exists() is False

    assert values == [
        "root/child",
        "root/child/grandchild",
        "root",
    ]


# ----------------------------------------------------------------------
def test_Constant():
    parent = CreatePathMock(
        Path("root"),
        exists=True,
    )

    child = parent / "child"
    grandchild = child / "grandchild"

    assert parent.exists() is True
    assert child.exists() is True
    assert grandchild.exists() is True
