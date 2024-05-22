import os
from os.path import join
import pytest

file_to_mutate_lines = [
    "def foo(a, b):",
    "    return a < b",
    "c = 1",
    "c += 1",
    "e = 1",
    "f = 3",
    "d = dict(e=f)",
    "g: int = 2",
]

EXPECTED_MUTANTS = 14

file_to_mutate_contents = '\n'.join(file_to_mutate_lines) + '\n'

test_file_contents = '''
from foo import *

def test_foo():
   assert foo(1, 2) is True
   assert foo(2, 2) is False

   assert c == 2
   assert e == 1
   assert f == 3
   assert d == dict(e=f)
   assert g == 2
'''


@pytest.fixture
def filesystem(tmpdir):
    create_filesystem(tmpdir, file_to_mutate_contents, test_file_contents)

    yield tmpdir

    # This is a hack to get pony to forget about the old db file
    # otherwise Pony thinks we've already created the tables
    import mutmut.cache
    mutmut.cache.db.provider = None
    mutmut.cache.db.schema = None


@pytest.fixture
def single_mutant_filesystem(tmpdir):
    create_filesystem(tmpdir, "def foo():\n    return 1\n", "from foo import *\ndef test_foo():\n    assert foo() == 1")

    yield tmpdir

    # This is a hack to get pony to forget about the old db file
    # otherwise Pony thinks we've already created the tables
    import mutmut.cache
    mutmut.cache.db.provider = None
    mutmut.cache.db.schema = None


@pytest.fixture
def surviving_mutants_filesystem(tmpdir):
    foo_py = """
def foo(a, b):
    result = a + b
    return result
"""

    test_py = """
def test_nothing(): assert True
"""

    create_filesystem(tmpdir, foo_py, test_py)

    yield tmpdir

    # This is a hack to get pony to forget about the old db file
    # otherwise Pony thinks we've already created the tables
    import mutmut.cache
    mutmut.cache.db.provider = None
    mutmut.cache.db.schema = None


def create_filesystem(tmpdir, file_to_mutate, test_file):
    test_dir = str(tmpdir)
    os.chdir(test_dir)

    # hammett is almost 5x faster than pytest. Let's use that instead.
    with open(join(test_dir, 'setup.cfg'), 'w') as f:
        f.write("""
[mutmut]
runner=python -m hammett -x
""")

    with open(join(test_dir, "foo.py"), 'w') as f:
        f.write(file_to_mutate)

    os.mkdir(join(test_dir, "tests"))

    with open(join(test_dir, "tests", "test_foo.py"), 'w') as f:
        f.write(test_file)
