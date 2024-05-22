import os
from os import mkdir
from os.path import join

import pytest

from tests.filesystem_fixture_setup import filesystem
from mutmut.helpers.progress import Progress
from mutmut.cli.helper.utils import python_source_files, read_coverage_data


# mock of Config for ease of testing
class MockProgress(Progress):
    def __init__(self, killed_mutants, surviving_mutants,
                 surviving_mutants_timeout, suspicious_mutants, **_):
        super(MockProgress, self).__init__(total=0, output_legend={}, no_progress=False)
        self.killed_mutants = killed_mutants
        self.surviving_mutants = surviving_mutants
        self.surviving_mutants_timeout = surviving_mutants_timeout
        self.suspicious_mutants = suspicious_mutants


@pytest.mark.parametrize(
    'killed, survived, timeout, suspicious, return_code', [
        (0, 0, 0, 0, 0),
        (0, 0, 0, 1, 8),
        (0, 0, 1, 0, 4),
        (0, 0, 1, 1, 12),
        (0, 1, 0, 0, 2),
        (0, 1, 0, 1, 10),
        (0, 1, 1, 0, 6),
        (0, 1, 1, 1, 14),
        (1, 0, 0, 0, 0),
        (1, 0, 0, 1, 8),
        (1, 0, 1, 0, 4),
        (1, 0, 1, 1, 12),
        (1, 1, 0, 0, 2),
        (1, 1, 0, 1, 10),
        (1, 1, 1, 0, 6),
        (1, 1, 1, 1, 14)
    ]
)
def test_compute_return_code(killed, survived, timeout, suspicious, return_code):
    assert (MockProgress(killed, survived, timeout, suspicious).compute_exit_code()) == return_code
    assert (MockProgress(killed, survived, timeout, suspicious).compute_exit_code(Exception())) == return_code + 1


@pytest.mark.parametrize(
    'killed, survived, timeout, suspicious', [
        (0, 0, 0, 0),
        (1, 1, 1, 1),
    ]
)
def test_compute_return_code_ci(killed, survived, timeout, suspicious):
    assert (MockProgress(killed, survived, timeout, suspicious).compute_exit_code(ci=True)) == 0
    assert (MockProgress(killed, survived, timeout, suspicious).compute_exit_code(Exception(), ci=True)) == 1


def test_read_coverage_data(filesystem):
    assert read_coverage_data() == {}


@pytest.mark.parametrize(
    "expected, source_path, tests_dirs",
    [
        (["foo.py"], "foo.py", []),
        ([os.path.join(".", "foo.py"),
          os.path.join(".", "tests", "test_foo.py")], ".", []),
        ([os.path.join(".", "foo.py")], ".", [os.path.join(".", "tests")])
    ]
)
def test_python_source_files(expected, source_path, tests_dirs, filesystem):
    assert list(python_source_files(source_path, tests_dirs)) == expected


def test_python_source_files__with_paths_to_exclude(tmpdir):
    tmpdir = str(tmpdir)
    # arrange
    paths_to_exclude = ['entities*']

    project_dir = join(tmpdir, 'project')
    service_dir = join(project_dir, 'services')
    entities_dir = join(project_dir, 'entities')
    mkdir(project_dir)
    mkdir(service_dir)
    mkdir(entities_dir)

    with open(join(service_dir, 'entities.py'), 'w'):
        pass

    with open(join(service_dir, 'main.py'), 'w'):
        pass

    with open(join(service_dir, 'utils.py'), 'w'):
        pass

    with open(join(entities_dir, 'user.py'), 'w'):
        pass

    # act, assert
    assert set(python_source_files(project_dir, [], paths_to_exclude)) == {
        os.path.join(project_dir, 'services', 'main.py'),
        os.path.join(project_dir, 'services', 'utils.py'),
    }
