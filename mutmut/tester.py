import multiprocessing
import os
import shlex
import subprocess
from copy import copy as copy_obj
from io import (
    open,
    TextIOBase,
)
from shutil import copy
from threading import (
    Timer,
    Thread,
)
from time import time
from typing import Callable, Dict, List, Optional

from mutmut.helpers.config import Config
from mutmut.helpers.context import Context
from mutmut.helpers.progress import *
from mutmut.helpers.relativemutationid import RelativeMutationID
from mutmut.mutator.mutator import Mutator

if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())
try:
    import mutmut_config
except ImportError:
    mutmut_config = None

CYCLE_PROCESS_AFTER = 100
hammett_prefix = 'python -m hammett '


def run_mutation_tests(
        config: Config,
        progress: Progress,
        mutations_by_file: Dict[str, List[RelativeMutationID]],
):
    # Need to explicitly use the spawn method for python < 3.8 on macOS
    mp_ctx = multiprocessing.get_context('spawn')

    mutants_queue = mp_ctx.Queue(maxsize=100)
    add_to_active_queues(mutants_queue)
    queue_mutants_thread = Thread(
        target=queue_mutants,
        name='queue_mutants',
        daemon=True,
        kwargs=dict(
            progress=progress,
            config=config,
            mutants_queue=mutants_queue,
            mutations_by_file=mutations_by_file,
        )
    )
    queue_mutants_thread.start()

    test_lock = multiprocessing.Lock()
    threads = []
    thread_range = range(4)
    for _ in thread_range:
        results_queue = mp_ctx.Queue(maxsize=100)
        add_to_active_queues(results_queue)
        threads.append((create_worker(mp_ctx, test_lock, mutants_queue, results_queue), results_queue))

    while True:
        thread_status = [False] * len(threads)
        for i, (thread, results_queue) in enumerate(threads):
            thread_result = command_results(mp_ctx, test_lock, mutants_queue, results_queue, thread,
                                            config, progress)
            thread_status[i] = thread_result
        if all(thread_status):
            break
        for i, status in enumerate(reversed(thread_status)):
            if status:
                threads.pop(len(thread_status) - 1 - i)

    # Cleanup Backup files
    if mutations_by_file:
        cleanup_backups(mutations_by_file.keys())


def cleanup_backups(filenames):
    for filename in filenames:
        if os.path.isfile(f'{filename}.bak'):
            os.remove(f'{filename}.bak')

def create_worker(mp_ctx, test_lock, mutants_queue, results_queue):
    t = mp_ctx.Process(
        target=check_mutants,
        name='check_mutants',
        daemon=True,
        kwargs=dict(
            mutants_queue=mutants_queue,
            results_queue=results_queue,
            test_lock=test_lock,
            cycle_process_after=CYCLE_PROCESS_AFTER
        )
    )
    t.start()
    return t


def command_results(mp_ctx, test_lock, mutants_queue, results_queue, t, config: Config, progress: Progress):
    from mutmut.cache import update_mutant_status

    command, status, filename, mutation_id = results_queue.get()
    if command == 'end':
        t.join()
        return True

    elif command == 'cycle':
        t = create_worker(mp_ctx, test_lock, mutants_queue, results_queue)
        return False

    elif command == 'progress':
        handle_progress(status, config, progress)
        return False

    else:
        assert command == 'status'
        progress.register(status)
        update_mutant_status(file_to_mutate=filename, mutation_id=mutation_id, status=status,
                             tests_hash=config.hash_of_tests)
        return False


def handle_progress(status, config, progress):
    if not config.swallow_output:
        print(status, end='', flush=True)
    elif not config.no_progress:
        progress.print()


class SkipException(Exception):
    pass


def check_mutants(mutants_queue, results_queue, test_lock, cycle_process_after):
    def feedback(line):
        results_queue.put(('progress', line, None, None))

    did_cycle = False

    try:
        count = 0
        while True:
            command, context = mutants_queue.get()
            if command == 'end':
                mutants_queue.put(('end', None))
                break

            status = run_mutation(context, feedback, test_lock)

            results_queue.put(('status', status, context.filename, context.mutation_id))
            count += 1
            if count == cycle_process_after:
                results_queue.put(('cycle', None, None, None))
                did_cycle = True
                break
    finally:
        if not did_cycle:
            results_queue.put(('end', None, None, None))


def run_mutation(context: Context, callback, test_lock) -> str:
    """
    :return: (computed or cached) status of the tested mutant, one of mutant_statuses
    """
    from mutmut.cache import cached_mutation_status
    cached_status = cached_mutation_status(context.filename, context.mutation_id, context.config.hash_of_tests)

    if cached_status != UNTESTED and context.config.total != 1:
        return cached_status

    config = context.config
    # Pre Mutation
    status = execute_pre_mutation(context)
    if status is not None:
        return status
    execute_config_pre_mutation(config, callback)

    mutator = Mutator(context)

    try:
        mutator.mutate_file(backup=True, test_lock=test_lock)
        # Execute Tests
        return execute_tests_on_mutation(config, callback)

    except SkipException:
        return SKIPPED

    finally:
        copy(f'{mutator.context.filename}.bak', mutator.context.filename)
        test_lock.release()
        config.test_command = config._default_test_command  # reset test command to its default in the case it was altered in a hook
        # Post Mutation
        execute_config_post_mutation(config, callback)


def execute_pre_mutation(context: Context):
    if hasattr(mutmut_config, 'pre_mutation'):
        context.current_line_index = context.mutation_id.line_number
        try:
            mutmut_config.pre_mutation(context=context)
        except SkipException:
            return SKIPPED
        if context.skip:
            return SKIPPED
    return None


def execute_config_pre_mutation(config: Config, callback):
    if config.pre_mutation:
        result = subprocess.check_output(config.pre_mutation, shell=True).decode().strip()
        if result and not config.swallow_output:
            callback(result)


def execute_tests_on_mutation(config: Config, callback):
    start = time()
    try:
        survived = tests_pass(config=config, callback=callback)
        if should_rerun_tests(config, survived):
            # rerun the whole test suite to be sure the mutant can not be killed by other tests
            config.test_command = config._default_test_command
            survived = tests_pass(config=config, callback=callback)
    except TimeoutError:
        return BAD_TIMEOUT

    return determine_tests_result(config, start, survived)


def should_rerun_tests(config: Config, survived):
    # Determines whether tests should be rerun based on the configuration and test results.
    return survived and config.test_command != config._default_test_command and config.rerun_all


def determine_tests_result(config: Config, start, survived):
    time_elapsed = time() - start
    if not survived and time_elapsed > config.test_time_base + (
            config.baseline_time_elapsed * config.test_time_multiplier
    ):
        return OK_SUSPICIOUS

    if survived:
        return BAD_SURVIVED
    else:
        return OK_KILLED


def execute_config_post_mutation(config: Config, callback):
    if config.post_mutation:
        result = subprocess.check_output(config.post_mutation, shell=True).decode().strip()
        if result and not config.swallow_output:
            callback(result)


def hammett_tests_pass(config: Config, callback) -> bool:
    # noinspection PyUnresolvedReferences
    from hammett import main_cli
    modules_before = set(sys.modules.keys())

    # set up timeout
    import _thread
    from threading import (
        Timer,
        current_thread,
        main_thread,
    )

    timed_out = False

    def timeout():
        _thread.interrupt_main()
        nonlocal timed_out
        timed_out = True

    assert current_thread() is main_thread()
    timer = Timer(config.baseline_time_elapsed * 10, timeout)
    timer.daemon = True
    timer.start()

    # Run tests
    try:
        returncode = run_hammett_tests(callback, main_cli, timer, config)
    except KeyboardInterrupt:
        handle_keyboard_interrupt(timer, timed_out)

    unload_modules(modules_before, config)

    return returncode == 0


class StdOutRedirect(TextIOBase):
    def __init__(self, callback):
        self.callback = callback

    def write(self, s):
        self.callback(s)
        return len(s)


def run_hammett_tests(callback, main_cli, timer, config: Config):
    redirect = StdOutRedirect(callback)
    sys.stdout = redirect
    sys.stderr = redirect
    returncode = main_cli(shlex.split(config.test_command[len(hammett_prefix):]))
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    timer.cancel()
    return returncode


def handle_keyboard_interrupt(timer, timed_out):
    timer.cancel()
    if timed_out:
        raise TimeoutError('In process tests timed out')
    raise


def unload_modules(modules_before, config: Config):
    modules_to_force_unload = {x.partition(os.sep)[0].replace('.py', '') for x in config.paths_to_mutate}

    for module_name in sorted(set(sys.modules.keys()) - set(modules_before), reverse=True):
        if should_unload(module_name, modules_to_force_unload):
            del sys.modules[module_name]


def should_unload(module_name, modules_to_force_unload):
    return any(module_name.startswith(x) for x in modules_to_force_unload) or module_name.startswith(
        'tests') or module_name.startswith('django')


def popen_streaming_output(
        cmd: str, callback: Callable[[str], None], timeout: Optional[float] = None
) -> int:
    """Open a subprocess and stream its output without hard-blocking.

    :param cmd: the command to execute within the subprocess
    :param callback: function that intakes the subprocess' stdout line by line.
        It is called for each line received from the subprocess' stdout stream.
    :param timeout: the timeout time of the subprocess
    :raises TimeoutError: if the subprocess' execution time exceeds
        the timeout time
    :return: the return code of the executed subprocess
    """
    if os.name == 'nt':  # pragma: no cover
        process, stdout = start_windows_process(cmd)
    else:
        process, stdout = start_other_os_process(cmd)

    # python 2-3 agnostic process timer
    timer = Timer(timeout, kill, [process])
    timer.daemon = True
    timer.start()

    while process.returncode is None:
        stream_output(stdout, callback)
        if not timer.is_alive():
            raise TimeoutError("subprocess running command '{}' timed out after {} seconds".format(cmd, timeout))
        process.poll()

    # we have returned from the subprocess cancel the timer if it is running
    timer.cancel()

    return process.returncode


def start_windows_process(cmd):
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
    )
    stdout = process.stdout
    return process, stdout


def start_other_os_process(cmd):
    master, slave = os.openpty()
    process = subprocess.Popen(
        shlex.split(cmd, posix=True),
        stdout=slave,
        stderr=slave
    )
    stdout = os.fdopen(master)
    os.close(slave)
    return process, stdout


def kill(process_):
    """Kill the specified process on Timer completion"""
    try:
        process_.kill()
    except OSError:
        pass


def stream_output(stdout, callback):
    try:
        if os.name == 'nt':  # pragma: no cover
            stream_windows_output(stdout, callback)
        else:
            stream_other_os_output(stdout, callback)
    except OSError:
        # This seems to happen on some platforms, including TravisCI.
        # It seems like it's ok to just let this pass here, you just
        # won't get as nice feedback.
        pass


def stream_windows_output(stdout, callback):
    line = stdout.readline()
    # windows gives readline() raw stdout as a b''
    # need to decode it
    line = line.decode("utf-8")
    if line:  # ignore empty strings and None
        callback(line)


def stream_other_os_output(stdout, callback):
    while True:
        line = stdout.readline()
        if not line:
            break
        callback(line)


def tests_pass(config: Config, callback) -> bool:
    """
    :return: :obj:`True` if the tests pass, otherwise :obj:`False`
    """
    if config.using_testmon:
        copy('.testmondata-initial', '.testmondata')

    use_special_case = True

    # Special case for hammett! We can do in-process test running which is much faster
    if use_special_case and config.test_command.startswith(hammett_prefix):
        return hammett_tests_pass(config, callback)

    returncode = popen_streaming_output(config.test_command, callback, timeout=config.baseline_time_elapsed * 10)
    return returncode not in (1, 2)


# List of active multiprocessing queues
_active_queues = []


def add_to_active_queues(queue):
    _active_queues.append(queue)


def close_active_queues():
    for queue in _active_queues:
        queue.close()


def queue_mutants(
        *,
        progress: Progress,
        config: Config,
        mutants_queue,
        mutations_by_file: Dict[str, List[RelativeMutationID]],
):
    from mutmut.cache import get_cached_mutation_statuses

    try:
        index = 0
        for filename, mutations in mutations_by_file.items():
            cached_mutation_statuses = get_cached_mutation_statuses(filename, mutations, config.hash_of_tests)
            with open(filename) as f:
                source = f.read()
            for mutation_id in mutations:
                cached_status = cached_mutation_statuses.get(mutation_id)
                if cached_status != UNTESTED:
                    progress.register(cached_status)
                    continue
                context = Context(
                    mutation_id=mutation_id,
                    filename=filename,
                    dict_synonyms=config.dict_synonyms,
                    config=copy_obj(config),
                    source=source,
                    index=index,
                )
                mutants_queue.put(('mutant', context))
                index += 1
    finally:
        mutants_queue.put(('end', None))
