# ----------------------------------------------------------------------
# |
# |  PathMock.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-21 13:59:01
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality that is useful when mocking `Path` objects"""

from pathlib import Path
from typing import Any
from unittest import mock


# ----------------------------------------------------------------------
def CreatePathMock(
    path: Path,
    **mocked_path_attributes: Any,
) -> mock.MagicMock:
    """Mocks a `Path` object so that any children created from the object mock the same attributes."""

    original_truediv_func = path.__truediv__

    # ----------------------------------------------------------------------
    def CreateChildPathInstance(
        mocked_instance: mock.MagicMock,  # pylint: disable=unused-argument
        child: Any,
    ) -> mock.MagicMock:
        return CreatePathMock(original_truediv_func(child), **mocked_path_attributes)

    # ----------------------------------------------------------------------

    new_mock = mock.MagicMock(
        wraps=path,
    )

    new_mock.__truediv__ = CreateChildPathInstance

    for attribute_name, attribute_mock_value in mocked_path_attributes.items():
        if callable(attribute_mock_value):
            original_attribute_mock_value = attribute_mock_value

            # ----------------------------------------------------------------------
            def CustomDecoratedMockFunc(
                *args,
                original_attribute_mock_value=original_attribute_mock_value,
                **kwargs,
            ):
                return original_attribute_mock_value(path, *args, **kwargs)

            # ----------------------------------------------------------------------

            attribute_mock_value = CustomDecoratedMockFunc  # type: ignore

        elif callable(getattr(path, attribute_name)):
            original_attribute_mock_value = attribute_mock_value

            # ----------------------------------------------------------------------
            def ConstantDecoratedMockFunc(*args, **kwargs):  # pylint: disable=unused-argument
                return original_attribute_mock_value

            # ----------------------------------------------------------------------

            attribute_mock_value = ConstantDecoratedMockFunc

        setattr(new_mock, attribute_name, attribute_mock_value)

    return new_mock
