# ----------------------------------------------------------------------
# |
# |  Add_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-08 09:07:51
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Unit tests for Add"""

import os
import sys

from pathlib import Path

from Common_Foundation.ContextlibEx import ExitStack


# ----------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0]), sys.path[0]

    from Add import Add


# ----------------------------------------------------------------------
def test_Positive():
    assert Add(1, 2) == 3
    assert Add(1, 23) == 24


# ----------------------------------------------------------------------
def test_Negative():
    assert Add(2, -10) == -8
