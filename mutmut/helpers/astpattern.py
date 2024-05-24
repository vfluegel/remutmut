import re

from parso import parse


class InvalidASTPatternException(Exception):
    pass


class ASTPattern:
    def __init__(self, source, **definitions):
        if definitions is None:
            definitions = {}
        source = source.strip()

        self.definitions = definitions

        self.module = parse(source)

        self.markers = []

        self.parse_markers(self.module)

        pattern_nodes = [x['node'] for x in self.markers if x['name'] == 'match' or x['name'] == '']
        if len(pattern_nodes) != 1:
            raise InvalidASTPatternException("Found more than one match node. Match nodes are nodes with an empty name or with the explicit name 'match'")
        self.pattern = pattern_nodes[0]
        self.marker_type_by_id = {id(x['node']): x['marker_type'] for x in self.markers}

    def get_leaf(self, line, column, of_type=None):
        r = self.module.children[0].get_leaf_for_position((line, column))
        while of_type is not None and r.type != of_type:
            r = r.parent
        return r

    def parse_group_of_markers(self, node_list):
        for node in node_list:
            self.parse_markers(node)

    def parse_markers(self, node):
        if hasattr(node, '_split_prefix'):
            self.parse_group_of_markers(node._split_prefix())

        if hasattr(node, 'children'):
            self.parse_group_of_markers(node.children)

        if node.type == 'comment':
            self.process_comment(node)

    def process_comment(self, node):
        line, column = node.start_pos
        for match in re.finditer(r'\^(?P<value>[^\^]*)', node.value):
            name = match.groupdict()['value'].strip()
            d = self.definitions.get(name, {})
            assert set(d.keys()) | {'of_type', 'marker_type'} == {'of_type', 'marker_type'}
            self.markers.append(dict(
                node=self.get_leaf(line - 1, column + match.start(), of_type=d.get('of_type')),
                marker_type=d.get('marker_type'),
                name=name,
            ))

    def matches(self, node, pattern=None, skip_child=None):
        if pattern is None:
            pattern = self.pattern

        check_value = True
        check_children = True

        # Match type based on the name, so _keyword matches all keywords.
        # Special case for _all that matches everything
        if self.is_special_all_case(pattern, node):
            check_value = False

        # The advanced case where we've explicitly marked up a node with
        # the accepted types
        elif self.is_marked_up(pattern):
            check_value = False
            check_children = False

        # Check node type strictly
        elif pattern.type != node.type:
            return False

        # Match children
        if (self.should_check_value(check_children, 'children', pattern) and
                not self.match_children(pattern, node, skip_child)):
            return False

        # Node value
        if self.should_check_value(check_value, 'value', pattern) and pattern.value != node.value:
            return False

        # Parent
        if pattern.parent.type != 'file_input' and skip_child != node:  # top level matches nothing
            return self.matches(node=node.parent, pattern=pattern.parent, skip_child=node)

        return True

    def match_children(self, pattern, node, skip_child):
        if len(pattern.children) != len(node.children):
            return False

        for pattern_child, node_child in zip(pattern.children, node.children):
            if node_child is skip_child:  # prevent infinite recursion
                continue

            if not self.matches(node=node_child, pattern=pattern_child, skip_child=node_child):
                return False

        return True

    @staticmethod
    def should_check_value(check, attribute, pattern):
        return check and hasattr(pattern, attribute)

    @staticmethod
    def is_special_all_case(pattern, node):
        return pattern.type == 'name' and pattern.value.startswith('_') and pattern.value[1:] in ('any', node.type)

    def is_marked_up(self, pattern):
        return id(pattern) in self.marker_type_by_id and self.marker_type_by_id[id(pattern)] in (pattern.type, 'any')

