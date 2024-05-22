# -*- coding: utf-8 -*-

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, ANY

import pytest
from click.testing import CliRunner

from tests.filesystem_fixture_setup import (
    filesystem,
    surviving_mutants_filesystem,
    single_mutant_filesystem,
    file_to_mutate_contents,
    test_file_contents,
    EXPECTED_MUTANTS)
from mutmut import __version__
from mutmut.mutator.mutator_helper import MutatorHelper
from mutmut.tester.tester import Tester
from mutmut.constants import MUTANT_STATUSES
from mutmut.__main__ import climain


def test_print_version():
    assert CliRunner().invoke(climain, ['version']).output.strip() == f'mutmut version {__version__}'


def test_simple_apply(filesystem):
    result = CliRunner().invoke(climain, ['run', '-s', '--paths-to-mutate=foo.py', "--test-time-base=15.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0

    result = CliRunner().invoke(climain, ['apply', '1'], catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    with open(os.path.join(str(filesystem), 'foo.py')) as f:
        assert f.read() != file_to_mutate_contents


def test_simply_apply_with_backup(filesystem):
    result = CliRunner().invoke(climain, ['run', '-s', '--paths-to-mutate=foo.py', "--test-time-base=15.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0

    result = CliRunner().invoke(climain, ['apply', '--backup', '1'], catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    with open(os.path.join(str(filesystem), 'foo.py')) as f:
        assert f.read() != file_to_mutate_contents
    with open(os.path.join(str(filesystem), 'foo.py.bak')) as f:
        assert f.read() == file_to_mutate_contents


def test_specify_processes(filesystem, monkeypatch):
    tester_run_mock = MagicMock()
    monkeypatch.setattr(Tester, 'run_mutation_tests', tester_run_mock)

    CliRunner().invoke(climain, ['run', '-s', '--paths-to-mutate=foo.py', "--test-time-base=15.0",
                                 "--test-processes=4"], catch_exceptions=False)

    tester_run_mock.assert_called_with(test_processes=4, config=ANY, progress=ANY, mutations_by_file=ANY)


def test_multiprocess_no_surviving_mutants(filesystem):
    result = CliRunner().invoke(climain, ['run', '-s', '--paths-to-mutate=foo.py', "--test-time-base=15.0",
                                          "--test-processes=4"], catch_exceptions=False)
    assert result.exit_code == 0
    no_surviving_result_check_helper()


def no_surviving_result_check_helper():
    result = CliRunner().invoke(climain, ['results'], catch_exceptions=False)
    assert result.exit_code == 0
    assert result.output.strip() == u"""
To apply a mutant on disk:
    mutmut apply <id>

To show a mutant:
    mutmut show <id>
""".strip()


def test_full_run_no_surviving_mutants(filesystem):
    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    no_surviving_result_check_helper()


def test_full_run_no_surviving_mutants_junit(filesystem):
    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0

    surviving_junit_helper(filesystem, 0, 0)


def test_mutant_only_killed_after_rerun(filesystem):
    mutmut_config = filesystem / "mutmut_config.py"
    mutmut_config.write("""
def pre_mutation(context):
    context.config.test_command = "echo True"
""")
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0", "--rerun-all"],
                       catch_exceptions=False)
    no_surviving_result_check_helper()


def test_no_rerun_if_not_specified(filesystem):
    mutmut_config = filesystem / "mutmut_config.py"
    mutmut_config.write("""
def pre_mutation(context):
    context.config.test_command = "echo True"
""")
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"], catch_exceptions=False)
    result = CliRunner().invoke(climain, ['results'], catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    assert result.output.strip() == u"""
To apply a mutant on disk:
    mutmut apply <id>

To show a mutant:
    mutmut show <id>


Survived 🙁 (14)

---- foo.py (14) ----

1-14
""".strip()


def test_full_run_one_surviving_mutant(filesystem):
    with open(os.path.join(str(filesystem), "tests", "test_foo.py"), 'w') as f:
        f.write(test_file_contents.replace('assert foo(2, 2) is False', ''))

    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 2
    one_surviving_result_check_helper()


def test_multiprocess_one_surviving_mutant(filesystem):
    with open(os.path.join(str(filesystem), "tests", "test_foo.py"), 'w') as f:
        f.write(test_file_contents.replace('assert foo(2, 2) is False', ''))

    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0",
                                          "--test-processes=4"], catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 2
    one_surviving_result_check_helper()


def one_surviving_result_check_helper():
    result = CliRunner().invoke(climain, ['results'], catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    assert result.output.strip() == u"""
To apply a mutant on disk:
    mutmut apply <id>

To show a mutant:
    mutmut show <id>


Survived 🙁 (1)

---- foo.py (1) ----

1
""".strip()


def surviving_junit_helper(filesystem, failures, exit_code):
    with open(os.path.join(str(filesystem), "tests", "test_foo.py"), 'w') as f:
        f.write(test_file_contents.replace('assert foo(2, 2) is False\n', ''))

    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == exit_code
    check_junit_output(failures)


def check_junit_output(failures):
    result = CliRunner().invoke(climain, ['junitxml'], catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    root = ET.fromstring(result.output.strip())
    assert int(root.attrib['tests']) == EXPECTED_MUTANTS
    assert int(root.attrib['failures']) == failures
    assert int(root.attrib['errors']) == 0
    assert int(root.attrib['disabled']) == 0


def test_full_run_one_surviving_mutant_junit(filesystem):
    surviving_junit_helper(filesystem, 1, 2)


def test_full_run_all_suspicious_mutant(filesystem):
    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-multiplier=0.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 8
    result = CliRunner().invoke(climain, ['results'], catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    assert result.output.strip() == u"""
To apply a mutant on disk:
    mutmut apply <id>

To show a mutant:
    mutmut show <id>


Suspicious 🤔 ({EXPECTED_MUTANTS})

---- foo.py ({EXPECTED_MUTANTS}) ----

1-{EXPECTED_MUTANTS}
""".format(EXPECTED_MUTANTS=EXPECTED_MUTANTS).strip()


def test_full_run_all_suspicious_mutant_junit(filesystem):
    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-multiplier=0.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 8
    check_junit_output(0)


def test_use_coverage(filesystem):
    # first validate that mutmut without coverage detects a surviving mutant
    surviving_junit_helper(filesystem, 1, 2)

    # generate a `.coverage` file by invoking pytest
    subprocess.run([sys.executable, "-m", "pytest", "--cov=.", "foo.py"])
    assert os.path.isfile('.coverage')

    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0", "--use-coverage"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    assert '13/13  🎉 13  ⏰ 0  🤔 0  🙁 0' in repr(result.output)

    # remove existent path to check if an exception is thrown
    os.unlink(os.path.join(str(filesystem), 'foo.py'))
    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0", "--use-coverage"],
                                catch_exceptions=False)
    assert result.exit_code == 2


def test_use_patch_file(filesystem):
    patch_contents = """diff --git a/foo.py b/foo.py
index b9a5fb4..c6a496c 100644
--- a/foo.py
+++ b/foo.py
@@ -1,7 +1,7 @@
 def foo(a, b):
     return a < b
 c = 1
 c += 1
 e = 1
-f = 3
+f = 5
 d = dict(e=f)
\\ No newline at end of file
"""
    with open('patch', 'w') as f:
        f.write(patch_contents)

    result = CliRunner().invoke(climain,
                                ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0", "--use-patch-file=patch"],
                                catch_exceptions=False)
    print(repr(result.output))
    assert result.exit_code == 0
    assert '2/2  🎉 2  ⏰ 0  🤔 0  🙁 0' in repr(result.output)


def test_pre_and_post_mutation_hook(single_mutant_filesystem, tmpdir):
    test_dir = str(tmpdir)
    os.chdir(test_dir)
    result = CliRunner().invoke(
        climain, [
            'run',
            '--paths-to-mutate=foo.py',
            "--test-time-base=15.0",
            "-s",
            "--pre-mutation=echo pre mutation stub",
            "--post-mutation=echo post mutation stub",
        ], catch_exceptions=False)
    print(result.output)
    assert result.exit_code == 0
    assert "pre mutation stub" in result.output
    assert "post mutation stub" in result.output
    assert result.output.index("pre mutation stub") < result.output.index("post mutation stub")


def test_simple_output(filesystem):
    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--simple-output"], catch_exceptions=False)
    print(repr(result.output))
    assert '14/14  KILLED 14  TIMEOUT 0  SUSPICIOUS 0  SURVIVED 0  SKIPPED 0' in repr(result.output)


def test_output_result_ids(filesystem):
    # Generate the results
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--simple-output"], catch_exceptions=False)
    # Check the output for the parts that are zero
    for attribute in set(MUTANT_STATUSES.keys()) - {"killed"}:
        assert CliRunner().invoke(climain, ['result-ids', attribute], catch_exceptions=False).output.strip() == ""
    # Check that "killed" contains all IDs
    killed_list = " ".join(str(num) for num in range(1, 15))
    assert CliRunner().invoke(climain, ['result-ids', "killed"], catch_exceptions=False).output.strip() == killed_list


def test_enable_single_mutation_type(filesystem):
    result = CliRunner().invoke(climain, [
        'run', '--paths-to-mutate=foo.py', "--simple-output", "--enable-mutation-types=operator"
    ], catch_exceptions=False)
    print(repr(result.output))
    assert '3/3  KILLED 3  TIMEOUT 0  SUSPICIOUS 0  SURVIVED 0  SKIPPED 0' in repr(result.output)


def test_enable_multiple_mutation_types(filesystem):
    result = CliRunner().invoke(climain, [
        'run', '--paths-to-mutate=foo.py', "--simple-output", "--enable-mutation-types=operator,number"
    ], catch_exceptions=False)
    print(repr(result.output))
    assert '8/8  KILLED 8  TIMEOUT 0  SUSPICIOUS 0  SURVIVED 0  SKIPPED 0' in repr(result.output)


def test_disable_single_mutation_type(filesystem):
    result = CliRunner().invoke(climain, [
        'run', '--paths-to-mutate=foo.py', "--simple-output", "--disable-mutation-types=number"
    ], catch_exceptions=False)
    print(repr(result.output))
    assert '9/9  KILLED 9  TIMEOUT 0  SUSPICIOUS 0  SURVIVED 0  SKIPPED 0' in repr(result.output)


def test_disable_multiple_mutation_types(filesystem):
    result = CliRunner().invoke(climain, [
        'run', '--paths-to-mutate=foo.py', "--simple-output", "--disable-mutation-types=operator,number"
    ], catch_exceptions=False)
    print(repr(result.output))
    assert '6/6  KILLED 6  TIMEOUT 0  SUSPICIOUS 0  SURVIVED 0  SKIPPED 0' in repr(result.output)


@pytest.mark.parametrize(
    "option", ["--enable-mutation-types", "--disable-mutation-types"]
)
def test_select_unknown_mutation_type(option):
    result = CliRunner().invoke(
        climain,
        [
            "run",
            f"{option}=foo,bar",
        ]
    )
    assert result.exception.code == 2
    assert f"The following are not valid mutation types: bar, foo. Valid mutation types are: {', '.join(MutatorHelper().mutations_by_type.keys())}" in result.output, result.output


def test_enable_and_disable_mutation_type_are_exclusive():
    result = CliRunner().invoke(
        climain,
        [
            "run",
            "--enable-mutation-types=operator",
            "--disable-mutation-types=string",
        ]
    )
    assert result.exception.code == 2
    assert "You can't combine --disable-mutation-types and --enable-mutation-types" in result.output


@pytest.mark.parametrize(
    "mutation_type, expected_mutation",
    [
        ("expr_stmt", "result = None"),
        ("operator", "result = a - b"),
    ]
)
def test_show_mutant_after_run_with_disabled_mutation_types(surviving_mutants_filesystem, mutation_type,
                                                            expected_mutation):
    """Test for issue #234: ``mutmut show <id>`` did not show the correct mutant if ``mutmut run`` was
    run with ``--enable-mutation-types`` or ``--disable-mutation-types``."""
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', f'--enable-mutation-types={mutation_type}'],
                       catch_exceptions=False)
    result = CliRunner().invoke(climain, ['show', '1'])
    assert f"""
 def foo(a, b):
-    result = a + b
+    {expected_mutation}
     return result
""" in result.output


def test_run_multiple_times_with_different_mutation_types(filesystem):
    """Running multiple times with different mutation types enabled should append the new mutants to the cache without
    altering existing mutants."""
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', '--enable-mutation-types=number'],
                       catch_exceptions=False)
    result = CliRunner().invoke(climain, ['show', '1'])
    assert """
-c = 1
+c = 2
""" in result.output
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', '--enable-mutation-types=operator'],
                       catch_exceptions=False)
    result = CliRunner().invoke(climain, ['show', '1'])
    assert """
-c = 1
+c = 2
""" in result.output, "mutant ID has changed!"
    result = CliRunner().invoke(climain, ['show', '8'])
    assert """
-c += 1
+c -= 1
""" in result.output, "no new mutation types added!"


def test_show(surviving_mutants_filesystem):
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"], catch_exceptions=False)
    result = CliRunner().invoke(climain, ['show'])
    assert result.output.strip() == """
To apply a mutant on disk:
    mutmut apply <id>

To show a mutant:
    mutmut show <id>


Survived 🙁 (2)

---- foo.py (2) ----

1-2
""".strip()


def test_show_single_id(surviving_mutants_filesystem, testdata):
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"], catch_exceptions=False)
    result = CliRunner().invoke(climain, ['show', '1'])
    assert result.output.strip() == (testdata / "surviving_mutants_show_id_1.txt").read_text("utf8").strip()


def test_show_all(surviving_mutants_filesystem, testdata):
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"], catch_exceptions=False)
    result = CliRunner().invoke(climain, ['show', 'all'])
    assert result.output.strip() == (testdata / "surviving_mutants_show_all.txt").read_text("utf8").strip()


def test_show_for_file(surviving_mutants_filesystem, testdata):
    CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"], catch_exceptions=False)
    result = CliRunner().invoke(climain, ['show', 'foo.py'])
    assert result.output.strip() == (testdata / "surviving_mutants_show_foo_py.txt").read_text("utf8").strip()


def test_html_output(surviving_mutants_filesystem):
    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    CliRunner().invoke(climain, ['html'])
    assert os.path.isfile("html/index.html")
    with open("html/index.html") as f:
        assert f.read() == (
            '<h1>Mutation testing report</h1>'
            'Killed 0 out of 2 mutants'
            '<table><thead><tr><th>File</th><th>Total</th><th>Skipped</th><th>Killed</th><th>% killed</th><th>Survived</th></thead>'
            '<tr><td><a href="foo.py.html">foo.py</a></td><td>2</td><td>0</td><td>0</td><td>0.00</td><td>2</td>'
            '</table></body></html>')


def test_html_custom_output(surviving_mutants_filesystem):
    result = CliRunner().invoke(climain, ['run', '--paths-to-mutate=foo.py', "--test-time-base=15.0"],
                                catch_exceptions=False)
    print(repr(result.output))
    CliRunner().invoke(climain, ['html', '--directory', 'htmlmut'])
    assert os.path.isfile("htmlmut/index.html")
    with open("htmlmut/index.html") as f:
        assert f.read() == (
            '<h1>Mutation testing report</h1>'
            'Killed 0 out of 2 mutants'
            '<table><thead><tr><th>File</th><th>Total</th><th>Skipped</th><th>Killed</th><th>% killed</th><th>Survived</th></thead>'
            '<tr><td><a href="foo.py.html">foo.py</a></td><td>2</td><td>0</td><td>0</td><td>0.00</td><td>2</td>'
            '</table></body></html>')
