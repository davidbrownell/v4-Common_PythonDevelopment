# ----------------------------------------------------------------------
# |
# |  AddSubtract_IntegrationTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-08 09:15:44
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Integration tests for Add and Subtract"""

import os
import sys

from pathlib import Path

from Common_Foundation.ContextlibEx import ExitStack

# pylint: disable=invalid-name

# code_coverage: include = ../Add.py
# code_coverage: include = ../Subtract.py


# ----------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0]), sys.path[0]

    from Add import Add                     # pylint: disable=import-error
    from Subtract import Subtract           # pylint: disable=import-error


# ----------------------------------------------------------------------
def test():
    assert Add(10, Subtract(20, 3)) == 27
    assert Subtract(10, Add(20, 3)) == -13
