import os
import sys
from time import sleep, time
import pytest
from unittest.mock import MagicMock, patch, call

from mutmut.tester.tester import Tester
from mutmut.helpers.progress import OK_KILLED
from mutmut.helpers.context import Context

PYTHON = '"{}"'.format(sys.executable)


def check_mutants_stub(**kwargs):
    def run_mutation_stub(*_):
        sleep(0.15)
        return OK_KILLED

    tester = Tester()
    check_mutants_original = tester.check_mutants
    with patch('mutmut.tester.tester.Tester.run_mutation', run_mutation_stub):
        check_mutants_original(**kwargs)


class ConfigStub:
    hash_of_tests = None


config_stub = ConfigStub()


def test_run_mutation_tests_thread_synchronization(monkeypatch):
    # arrange
    total_mutants = 3
    cycle_process_after = 1

    tester = Tester()

    def queue_mutants_stub(**kwargs):
        for _ in range(total_mutants):
            kwargs['mutants_queue'].put(('mutant', Context(config=config_stub)))
        kwargs['mutants_queue'].put(('end', None))

    monkeypatch.setattr(tester.queue_manager, 'queue_mutants', queue_mutants_stub)

    def update_mutant_status_stub(**_):
        sleep(0.1)

    monkeypatch.setattr(tester, 'check_mutants', check_mutants_stub)
    monkeypatch.setattr('mutmut.cache.update_mutant_status', update_mutant_status_stub)
    monkeypatch.setattr('mutmut.tester.tester.CYCLE_PROCESS_AFTER', cycle_process_after)

    progress_mock = MagicMock()
    progress_mock.registered_mutants = 0

    def progress_mock_register(*_):
        progress_mock.registered_mutants += 1

    progress_mock.register = progress_mock_register

    # act
    tester.run_mutation_tests(config_stub, progress_mock, 2, None)

    # assert
    assert progress_mock.registered_mutants == total_mutants

    tester.queue_manager.close_active_queues()


def test_popen_streaming_output_timeout():
    start = time()
    tester = Tester()
    with pytest.raises(TimeoutError):
        tester.popen_streaming_output(
            PYTHON + ' -c "import time; time.sleep(4)"',
            lambda line: line, timeout=0.1,
        )

    assert (time() - start) < 3


def test_popen_streaming_output_stream():
    mock = MagicMock()
    tester = Tester()
    tester.popen_streaming_output(
        PYTHON + ' -c "print(\'first\'); print(\'second\')"',
        callback=mock
    )
    if os.name == 'nt':
        mock.assert_has_calls([call('first\r\n'), call('second\r\n')])
    else:
        mock.assert_has_calls([call('first\n'), call('second\n')])

    mock = MagicMock()
    tester = Tester()
    tester.popen_streaming_output(
        PYTHON + ' -c "import time; print(\'first\'); print(\'second\'); print(\'third\')"',
        callback=mock
    )
    if os.name == 'nt':
        mock.assert_has_calls([call('first\r\n'), call('second\r\n'), call('third\r\n')])
    else:
        mock.assert_has_calls([call('first\n'), call('second\n'), call('third\n')])

    mock = MagicMock()
    tester = Tester()
    tester.popen_streaming_output(
        PYTHON + ' -c "exit(0);"',
        callback=mock)
    mock.assert_not_called()
