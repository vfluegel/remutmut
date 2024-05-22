import unittest.mock as mock
from collections.abc import Iterator

import pytest

from mutmut.mutator.post_order_iterator import PostOrderIterator


class Node:
    def __init__(self, type="", value=""):
        self.type = type
        self.value = value


class NodeWithChildren(Node):

    def __init__(self, type="", value="", children=None):
        super().__init__(type, value)
        self.children = children if children else []


def patches(get_return_annotation_started=False, is_special_node=False, is_dynamic_import_node=False,
            should_update_line_index=False, is_a_dunder_whitelist_node=False, is_pure_annotation=False):
    return [
        mock.patch.object(PostOrderIterator, '_get_return_annotation_started',
                          return_value=get_return_annotation_started),
        mock.patch.object(PostOrderIterator, "_is_special_node", return_value=is_special_node),
        mock.patch.object(PostOrderIterator, "_is_dynamic_import_node", return_value=is_dynamic_import_node),
        mock.patch.object(PostOrderIterator, "_should_update_line_index", return_value=should_update_line_index),
        mock.patch.object(PostOrderIterator, "_is_a_dunder_whitelist_node", return_value=is_a_dunder_whitelist_node),
        mock.patch.object(PostOrderIterator, "_is_pure_annotation", return_value=is_pure_annotation),
    ]


def setup_patches(get_return_annotation_started=False, is_special_node=False, is_dynamic_import_node=False,
                  should_update_line_index=False, is_a_dunder_whitelist_node=False, is_pure_annotation=False):
    for patch in patches(get_return_annotation_started, is_special_node, is_dynamic_import_node,
                         should_update_line_index, is_a_dunder_whitelist_node, is_pure_annotation):
        patch.start()


def teardown_patches():
    for patch in patches():
        patch.stop()


def test_mutator_iterator_is_instance_of_iterator():
    iterator = PostOrderIterator(root_node=None, context=None)
    assert isinstance(iterator, Iterator)


def test_mutator_iterator_has_next_with_empty_collections():
    iterator = PostOrderIterator(root_node=None, context=None)
    assert not iterator._has_next()


def test_mutator_iterator_has_next_with_non_empty_collections():
    root = Node()
    iterator = PostOrderIterator(root_node=root, context=None)
    assert iterator._has_next()


def test_mutator_iterator_is_special_node_with_special_node_types():
    special_node_types = ['tfpdef', 'import_from', 'import_name']
    for node_type in special_node_types:
        node = Node(type=node_type)
        iterator = PostOrderIterator(root_node=node, context=None)
        assert iterator._is_special_node(node)


def test_mutator_iterator_is_special_node_with_non_special_node_types():
    iterator = PostOrderIterator(None, None)
    non_special_node_types = ['non_special', 'another_non_special']
    for node_type in non_special_node_types:
        node = Node(type=node_type)
        iterator = PostOrderIterator(root_node=node, context=None)
        assert not iterator._is_special_node(node)


def test_mutator_iterator_is_dynamic_import_node_with_dynamic_import_node():
    node = NodeWithChildren(type='atom_expr', children=[Node(type='name', value='__import__')])
    iterator = PostOrderIterator(node, None)
    assert iterator._is_dynamic_import_node(node)


def test_mutator_iterator_is_dynamic_import_node_with_non_dynamic_import_node():
    node = NodeWithChildren(type='non_atom_expr', children=[Node(type='name', value='__import__')])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_dynamic_import_node(node)

    node = NodeWithChildren(type='non_atom_expr', children=None)
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_dynamic_import_node(node)

    node = NodeWithChildren(type='non_atom_expr', children=[Node(type='no_name', value='__import__')])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_dynamic_import_node(node)

    node = NodeWithChildren(type='non_atom_expr', children=[Node(type='name', value='no__import__')])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_dynamic_import_node(node)


def test_mutator_iterator_is_a_dunder_whitelist_node_with_dunder_whitelist_node():
    node = NodeWithChildren(type='expr_stmt', children=[Node(type='name', value='__all__')])
    iterator = PostOrderIterator(node, None)
    assert iterator._is_a_dunder_whitelist_node(node)


def test_mutator_iterator_is_a_dunder_whitelist_node_with_non_dunder_whitelist_node():
    node = NodeWithChildren(type='non_expr_stmt', children=[Node(type='name', value='__all__')])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_a_dunder_whitelist_node(node)

    node = NodeWithChildren(type='expr_stmt', children=[Node(type='non_name', value='__all__')])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_a_dunder_whitelist_node(node)

    node = NodeWithChildren(type='expr_stmt', children=[Node(type='name', value='all__')])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_a_dunder_whitelist_node(node)

    node = NodeWithChildren(type='expr_stmt', children=[Node(type='name', value='__all')])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_a_dunder_whitelist_node(node)

    node = NodeWithChildren(type='expr_stmt', children=[Node(type='name', value='__non_whitelist__')])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_a_dunder_whitelist_node(node)


def test_mutator_iterator_is_pure_annotation_with_pure_annotation_node():
    node = NodeWithChildren(type='annassign', children=[Node(), Node()])
    iterator = PostOrderIterator(node, None)
    assert iterator._is_pure_annotation(node)


def test_mutator_iterator_is_pure_annotation_with_non_pure_annotation_node():
    node = NodeWithChildren(type='non_annassign', children=[Node(), Node()])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_pure_annotation(node)

    node = NodeWithChildren(type='annassign', children=[Node()])
    iterator = PostOrderIterator(node, None)
    assert not iterator._is_pure_annotation(node)


def test_mutator_iterator_check_node_type_and_value_with_matching_node():
    node = Node(type='operator', value='->')
    iterator = PostOrderIterator(node, None)
    assert iterator._check_node_type_and_value(node, 'operator', '->')


def test_mutator_iterator_check_node_type_and_value_with_non_matching_node():
    node = Node(type='operator', value='->')
    iterator = PostOrderIterator(node, None)
    assert not iterator._check_node_type_and_value(node, 'operator', ':')

    node = Node(type='operator', value='->')
    iterator = PostOrderIterator(node, None)
    assert not iterator._check_node_type_and_value(node, 'non_operator', '->')


def test_post_order_iterator_next_with_empty_collections():
    iterator = PostOrderIterator(None, None)
    with pytest.raises(StopIteration):
        iterator.__next__()


def test_post_order_iterator_next_with_single_node():
    node = Node()
    iterator = PostOrderIterator(node, None)
    assert iterator.__next__() == node


def test_post_order_iterator_next_with_multiple_nodes():
    setup_patches()
    child_node = Node()
    root_node = NodeWithChildren(children=[child_node])
    iterator = PostOrderIterator(root_node, mock.MagicMock())

    nodes_in_order = [child_node, root_node]

    for i, node in enumerate(iterator):
        assert node == nodes_in_order[i]

    teardown_patches()


def post_order_iterator_next_with_multiple_nodes_with_check(**check):
    setup_patches(**check)
    child_node = Node()
    root_node = NodeWithChildren(children=[child_node])
    iterator = PostOrderIterator(root_node, mock.MagicMock())

    nodes_in_order = [root_node]

    for i, node in enumerate(iterator):
        assert node == nodes_in_order[i]

    teardown_patches()


def test_post_order_iterator_next_with_multiple_nodes_annotation_started():
    """
    Child node is a return annotation node, so it should be skipped.
    """

    post_order_iterator_next_with_multiple_nodes_with_check(get_return_annotation_started=True)


def test_post_order_iterator_next_with_multiple_nodes_is_special_node():
    """
    Child node is a special node, so it should be skipped.
    """

    post_order_iterator_next_with_multiple_nodes_with_check(is_special_node=True)


def test_post_order_iterator_next_with_multiple_nodes_is_dynamic_import_node():
    """
    Child node is a special node, so it should be skipped.
    """

    post_order_iterator_next_with_multiple_nodes_with_check(is_dynamic_import_node=True)


def test_post_order_iterator_next_with_multiple_nodes_should_update_line_index():
    """
    Child node is a special node, so it should be skipped.
    """

    setup_patches(should_update_line_index=True)
    child_node = mock.MagicMock()
    root_node = NodeWithChildren(children=[child_node])
    iterator = PostOrderIterator(root_node, mock.MagicMock())

    nodes_in_order = [child_node, root_node]

    for i, node in enumerate(iterator):
        assert node == nodes_in_order[i]

    teardown_patches()


def test_post_order_iterator_next_with_multiple_nodes_is_a_dunder_whitelist_node():
    post_order_iterator_next_with_multiple_nodes_with_check(is_a_dunder_whitelist_node=True)


def test_post_order_iterator_next_with_multiple_nodes_is_a_pure_annotation():
    """
    Child node is a special node, so it should be skipped.
    """

    post_order_iterator_next_with_multiple_nodes_with_check(is_pure_annotation=True)
