from mutmut.mutations.and_or_test_mutation import AndOrTestMutation
from mutmut.mutations.argument_mutation import ArgumentMutation
from mutmut.mutations.decorator_mutation import DecoratorMutation
from mutmut.mutations.expression_mutation import ExpressionMutation
from mutmut.mutations.f_string_mutation import FStringMutation
from mutmut.mutations.keyword_mutation import KeywordMutation
from mutmut.mutations.lambda_mutation import LambdaMutation
from mutmut.mutations.name_mutation import NameMutation
from mutmut.mutations.number_mutation import NumberMutation
from mutmut.mutations.operator_mutation import OperatorMutation
from mutmut.mutations.string_mutation import StringMutation

try:
    import mutmut_config
except ImportError:
    mutmut_config = None


class MutatorHelper:

    def __init__(self):

        self.newline = {'formatting': [], 'indent': '', 'type': 'endl', 'value': ''}

        self.mutations_by_type = {
            'operator': ("value", OperatorMutation),
            'keyword': ("value", KeywordMutation),
            'number': ("value", NumberMutation),
            'name': ("value", NameMutation),
            'string': ("value", StringMutation),
            'fstring': ("children", FStringMutation),
            'argument': ("children", ArgumentMutation),
            'or_test': ("children", AndOrTestMutation),
            'and_test': ("children", AndOrTestMutation),
            'lambdef': ("children", LambdaMutation),
            'expr_stmt': ("children", ExpressionMutation),
            'decorator': ("children", DecoratorMutation),
            'annassign': ("children", ExpressionMutation),
        }

    @staticmethod
    def wrap_or_return_mutation_instance(new, old):
        if isinstance(new, list) and not isinstance(old, list):
            # multiple mutations
            return new

        return [new]
