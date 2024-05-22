from configparser import ConfigParser
from dataclasses import dataclass, field
from functools import wraps
from typing import Optional, Dict, List, Set
import toml


@dataclass
class Config:
    swallow_output: bool
    test_command: str
    _default_test_command: str = field(init=False)
    covered_lines_by_filename: Optional[Dict[str, set[Optional[int]]]]
    baseline_time_elapsed: float
    test_time_multiplier: float
    test_time_base: float
    dict_synonyms: List[str]
    total: int
    using_testmon: bool
    tests_dirs: List[str]
    hash_of_tests: str
    post_mutation: str
    pre_mutation: str
    coverage_data: Dict[str, Dict[int, List[str]]]
    paths_to_mutate: List[str]
    mutation_types_to_apply: Set[str]
    no_progress: bool
    ci: bool
    rerun_all: bool

    def __post_init__(self):
        self._default_test_command = self.test_command


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
