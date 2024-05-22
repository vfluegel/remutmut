from mutmut.helpers.relativemutationid import RelativeMutationID

ALL = RelativeMutationID(filename='%all%', line='%all%', index=-1, line_number=-1)

UNTESTED = 'untested'
OK_KILLED = 'ok_killed'
OK_SUSPICIOUS = 'ok_suspicious'
BAD_TIMEOUT = 'bad_timeout'
BAD_SURVIVED = 'bad_survived'
SKIPPED = 'skipped'

MUTANT_STATUSES = {
    "killed": OK_KILLED,
    "timeout": BAD_TIMEOUT,
    "suspicious": OK_SUSPICIOUS,
    "survived": BAD_SURVIVED,
    "skipped": SKIPPED,
    "untested": UNTESTED,
}


