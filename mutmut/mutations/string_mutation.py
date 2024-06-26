from mutmut.mutations.mutation import Mutation


class StringMutation(Mutation):
    def __init__(self):
        super().__init__('StringMutation')

    def mutate(self, value, **kwargs):
        prefix = value[:min(x for x in [value.find('"'), value.find("'")] if x != -1)]
        value = value[len(prefix):]

        if value.startswith('"""') or value.startswith("'''"):
            # We assume here that triple-quoted stuff are docs or other things
            # that mutation is meaningless for
            return prefix + value
        return prefix + value[0] + 'XX' + value[1:-1] + 'XX' + value[-1]
