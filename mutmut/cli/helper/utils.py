import fnmatch
import os
from os.path import isdir
from pathlib import Path
from shutil import copy
from typing import Iterator, List, Optional, Dict
from functools import wraps
from configparser import ConfigParser
import toml
import click
from glob2 import glob


def split_paths(paths):
    # This method is used to split paths that are separated by commas or colons
    for sep in [',', ':']:
        separated = list(filter(lambda p: Path(p).exists(), paths.split(sep)))
        if separated:
            return separated
    return None


def get_split_paths(p, test_paths):
    split = []

    for pt in test_paths:
        split.extend(glob(p + '/**/' + pt, recursive=True))

    return split


def copy_testmon_data(using_testmon):
    if using_testmon:
        copy('.testmondata', '.testmondata-initial')


def stop_creating_pyc_files():
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'


def check_file_exists(filename):
    if not os.path.exists(filename):
        raise click.BadArgumentUsage(f'File {filename} does not exist')


def python_source_files(path: str, tests_dirs: List[str], paths_to_exclude: Optional[List[str]] = None) \
        -> Iterator[str]:
    """Attempt to guess where the python source files to mutate are and yield
    their paths

    :param path: path to a python source file or package directory
    :param tests_dirs: list of directory paths containing test files
        (we do not want to mutate these!)
    :param paths_to_exclude: list of UNIX filename patterns to exclude

    :return: generator listing the paths to the python source files to mutate
    """
    paths_to_exclude = paths_to_exclude or []
    if isdir(path):
        yield from process_python_dir(path, paths_to_exclude, tests_dirs)
    else:
        yield path


def process_python_dir(path, paths_to_exclude, tests_dirs):
    for root, dirs, files in os.walk(path, topdown=True):
        for exclude_pattern in paths_to_exclude:
            dirs[:] = [d for d in dirs if not fnmatch.fnmatch(d, exclude_pattern)]
            files[:] = [f for f in files if not fnmatch.fnmatch(f, exclude_pattern)]

        dirs[:] = [d for d in dirs if os.path.join(root, d) not in tests_dirs]
        python_files = filter(lambda name: name.endswith('.py'), files)
        for filename in python_files:
            yield os.path.join(root, filename)


def read_patch_data(patch_file_path: str):
    try:
        # noinspection PyPackageRequirements
        import whatthepatch
    except ImportError as e:
        raise ImportError(
            'The --use-patch feature requires the whatthepatch library. Run "pip install --force-reinstall mutmut[patch]"') from e
    with open(patch_file_path) as f:
        diffs = whatthepatch.parse_patch(f.read())

    return {
        os.path.normpath(diff.header.new_path): {change.new for change in diff.changes if change.old is None}
        for diff in diffs if diff.changes
    }


def read_coverage_data() -> Dict[str, Dict[int, List[str]]]:
    """
    Reads the coverage database and returns a dictionary which maps the filenames to the covered lines and their contexts.
    """
    try:
        # noinspection PyPackageRequirements,PyUnresolvedReferences
        from coverage import Coverage
    except ImportError as e:
        raise ImportError(
            'The --use-coverage feature requires the coverage library. Run "pip install --force-reinstall mutmut[coverage]"') from e
    cov = Coverage('.coverage')
    cov.load()
    data = cov.get_data()
    return {filepath: data.contexts_by_lineno(filepath) for filepath in data.measured_files()}


def config_from_file(**defaults):
    def config_from_pyproject_toml() -> dict:
        try:
            return toml.load('pyproject.toml')['tool']['mutmut']
        except (FileNotFoundError, KeyError):
            return {}

    def config_from_setup_cfg() -> dict:
        config_parser = ConfigParser()
        config_parser.read('setup.cfg')

        try:
            return dict(config_parser['mutmut'])
        except KeyError:
            return {}

    config = config_from_pyproject_toml() or config_from_setup_cfg()

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            for k in list(kwargs.keys()):
                if not kwargs[k]:
                    kwargs[k] = config.get(k, defaults.get(k))
            f(*args, **kwargs)

        return wrapper

    return decorator
