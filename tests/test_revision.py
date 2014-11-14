from alembic.testing.fixtures import TestBase
from alembic.testing import eq_, assert_raises_message
from alembic.revision import RevisionMap, Revision, MultipleRevisions
from alembic.util import CommandError


class APITest(TestBase):
    def test_add_revision_one_head(self):
        map_ = RevisionMap(
            lambda: [
                Revision('a', ()),
                Revision('b', ('a',)),
                Revision('c', ('b',)),
            ]
        )
        eq_(map_.heads, ('c', ))

        map_.add_revision(Revision('d', ('c', )))
        eq_(map_.heads, ('d', ))

    def test_add_revision_two_head(self):
        map_ = RevisionMap(
            lambda: [
                Revision('a', ()),
                Revision('b', ('a',)),
                Revision('c1', ('b',)),
                Revision('c2', ('b',)),
            ]
        )
        eq_(map_.heads, ('c1', 'c2'))

        map_.add_revision(Revision('d1', ('c1', )))
        eq_(map_.heads, ('c2', 'd1'))

    def test_get_revision_head_single(self):
        map_ = RevisionMap(
            lambda: [
                Revision('a', ()),
                Revision('b', ('a',)),
                Revision('c', ('b',)),
            ]
        )
        eq_(map_.get_revision('head'), map_._revision_map['c'])

    def test_get_revision_base_single(self):
        map_ = RevisionMap(
            lambda: [
                Revision('a', ()),
                Revision('b', ('a',)),
                Revision('c', ('b',)),
            ]
        )
        eq_(map_.get_revision('base'), map_._revision_map['a'])

    def test_get_revision_head_multiple(self):
        map_ = RevisionMap(
            lambda: [
                Revision('a', ()),
                Revision('b', ('a',)),
                Revision('c1', ('b',)),
                Revision('c2', ('b',)),
            ]
        )
        assert_raises_message(
            MultipleRevisions,
            "Identifier 'head' corresponds to multiple revisions; "
            "please use get_revisions()",
            map_.get_revision, 'head'
        )

    def test_get_revision_base_multiple(self):
        map_ = RevisionMap(
            lambda: [
                Revision('a', ()),
                Revision('b', ('a',)),
                Revision('c', ()),
                Revision('d', ('c',)),
            ]
        )
        assert_raises_message(
            MultipleRevisions,
            "Identifier 'base' corresponds to multiple revisions; "
            "please use get_revisions()",
            map_.get_revision, 'base'
        )


class DownIterateTest(TestBase):
    def _assert_iteration(self, upper, lower, assertion, inclusive=True):
        eq_(
            [rev.revision for rev in
             self.map._iterate_revisions(upper, lower, inclusive=inclusive)],
            assertion
        )


class DiamondTest(DownIterateTest):
    def setUp(self):
        self.map = RevisionMap(
            lambda: [
                Revision('a', ()),
                Revision('b1', ('a',)),
                Revision('b2', ('a',)),
                Revision('c', ('b1', 'b2')),
                Revision('d', ('c',)),
            ]
        )

    def test_iterate_simple_diamond(self):
        self._assert_iteration(
            "d", "a",
            ["d", "c", "b1", "b2", "a"]
        )


class MultipleBranchTest(DownIterateTest):
    def setUp(self):
        self.map = RevisionMap(
            lambda: [
                Revision('a', ()),
                Revision('b1', ('a',)),
                Revision('b2', ('a',)),
                Revision('cb1', ('b1',)),
                Revision('cb2', ('b2',)),
                Revision('d1cb1', ('cb1',)),
                Revision('d2cb1', ('cb1',)),
                Revision('d1cb2', ('cb2',)),
                Revision('d2cb2', ('cb2',)),
                Revision('d3cb2', ('cb2',)),
                Revision('d1d2cb2', ('d1cb2', 'd2cb2'))
            ]
        )

    def test_iterate_from_merge_point(self):
        self._assert_iteration(
            "d1d2cb2", "a",
            ['d1d2cb2', 'd1cb2', 'd2cb2', 'cb2', 'b2', 'a']
        )

    def test_iterate_multiple_heads(self):
        self._assert_iteration(
            ["d2cb2", "d3cb2"], "a",
            ['d2cb2', 'd3cb2', 'cb2', 'b2', 'a']
        )

    def test_iterate_single_branch(self):
        self._assert_iteration(
            "d3cb2", "a",
            ['d3cb2', 'cb2', 'b2', 'a']
        )

    def test_same_branch_wrong_direction(self):
        # nodes b1 and d1cb1 are connected, but
        # db1cb1 is the descendant of b1
        assert_raises_message(
            CommandError,
            r"Revision\(s\) d1cb1 is not an ancestor of revision\(s\) b1",
            list,
            self.map._iterate_revisions('b1', 'd1cb1')
        )

    def test_distinct_branches(self):
        # nodes db2cb2 and b1 have no path to each other
        assert_raises_message(
            CommandError,
            r"Revision\(s\) b1 is not an ancestor of revision\(s\) d2cb2",
            list,
            self.map._iterate_revisions('d2cb2', 'b1')
        )

    def test_wrong_direction_to_base(self):
        assert_raises_message(
            CommandError,
            r"Revision\(s\) d1cb1 is not an ancestor of revision\(s\) base",
            list,
            self.map._iterate_revisions(None, 'd1cb1')
        )

        assert_raises_message(
            CommandError,
            r"Revision\(s\) d1cb1 is not an ancestor of revision\(s\) base",
            list,
            self.map._iterate_revisions((), 'd1cb1')
        )

class BranchTravellingTest(DownIterateTest):
    """test the order of revs when going along multiple branches.

    We want depth-first along branches, but then we want to
    terminate all branches at their branch point before continuing
    to the nodes preceding that branch.

    """

    def setUp(self):
        self.map = RevisionMap(
            lambda: [
                Revision('a1', ()),
                Revision('a2', ('a1',)),
                Revision('a3', ('a2',)),
                Revision('b1', ('a3',)),
                Revision('b2', ('a3',)),
                Revision('cb1', ('b1',)),
                Revision('cb2', ('b2',)),
                Revision('db1', ('cb1',)),
                Revision('db2', ('cb2',)),

                Revision('e1b1', ('db1',)),
                Revision('fe1b1', ('e1b1',)),

                Revision('e2b1', ('db1',)),
                Revision('e2b2', ('db2',)),
                Revision("merge", ('e2b1', 'e2b2'))
            ]
        )

    def test_two_branches_to_root(self):

        # here we want 'a3' as a "stop" branch point, but *not*
        # 'db1', as we don't have multiple traversals on db1
        self._assert_iteration(
            "merge", "a1",
            ['merge',
                'e2b1', 'db1', 'cb1', 'b1',  # e2b1 branch
                'e2b2', 'db2', 'cb2', 'b2',  # e2b2 branch
                'a3',  # both terminate at a3
                'a2', 'a1'  # finish out
            ]  # noqa
        )

    def test_two_branches_end_in_branch(self):
        self._assert_iteration(
            "merge", "b1",
            # 'b1' is local to 'e2b1'
            # branch so that is all we get
            ['merge', 'e2b1', 'db1', 'cb1', 'b1',

        ]  # noqa
        )

    def test_two_branches_end_behind_branch(self):
        self._assert_iteration(
            "merge", "a2",
            ['merge',
                'e2b1', 'db1', 'cb1', 'b1',  # e2b1 branch
                'e2b2', 'db2', 'cb2', 'b2',  # e2b2 branch
                'a3',  # both terminate at a3
                'a2'
            ]  # noqa
        )

    def test_three_branches_to_root(self):

        # in this case, both "a3" and "db1" are stop points
        self._assert_iteration(
            ["merge", "fe1b1"], "a1",
            ['merge',
                'e2b1',  # e2b1 branch
                'e2b2', 'db2', 'cb2', 'b2',  # e2b2 branch
                'fe1b1', 'e1b1',  # fe1b1 branch
                'db1',  # fe1b1 and e2b1 branches terminate at db1
                'cb1', 'b1',  # e2b1 branch continued....might be nicer
                              # if this was before the e2b2 branch...
                'a3',  # e2b1 and e2b2 branches terminate at a3
                'a2', 'a1'  # finish out
            ]  # noqa
        )

    def test_three_branches_end_in_single_branch(self):

        # in this case, both "a3" and "db1" are stop points
        self._assert_iteration(
            ["merge", "fe1b1"], "e1b1",
            ['merge',
                'fe1b1', 'e1b1',  # fe1b1 branch
            ]  # noqa
        )

    def test_three_branches_end_multiple_bases(self):

        # in this case, both "a3" and "db1" are stop points
        self._assert_iteration(
            ["merge", "fe1b1"], ["cb1", "cb2"],
            [
                'merge',
                'e2b1',
                'e2b2', 'db2', 'cb2',
                'fe1b1', 'e1b1',
                'db1',
                'cb1'
            ]
        )

    def test_three_branches_end_multiple_bases_exclusive(self):

        self._assert_iteration(
            ["merge", "fe1b1"], ["cb1", "cb2"],
            [
                'merge',
                'e2b1',
                'e2b2', 'db2',
                'fe1b1', 'e1b1',
                'db1',
            ],
            inclusive=False
        )

    def test_detect_invalid_head_selection(self):
        # db1 is an ancestor of fe1b1
        assert_raises_message(
            CommandError,
            "Requested head revision fe1b1 overlaps "
            "with other requested head revisions",
            list,
            self.map._iterate_revisions(["db1", "b2", "fe1b1"], ())
        )

    def test_three_branches_end_multiple_bases_exclusive_blank(self):
        self._assert_iteration(
            ["e2b1", "b2", "fe1b1"], (),
            [
                'e2b1',
                'b2',
                'fe1b1', 'e1b1',
                'db1', 'cb1', 'b1', 'a3', 'a2', 'a1'
            ],
            inclusive=False
        )


class MultipleBaseTest(DownIterateTest):
    def setUp(self):
        self.map = RevisionMap(
            lambda: [
                Revision('base1', ()),
                Revision('base2', ()),
                Revision('base3', ()),

                Revision('a1a', ('base1',)),
                Revision('a1b', ('base1',)),
                Revision('a2', ('base2',)),
                Revision('a3', ('base3',)),

                Revision('b1a', ('a1a',)),
                Revision('b1b', ('a1b',)),
                Revision('b2', ('a2',)),
                Revision('b3', ('a3',)),

                Revision('c2', ('b2',)),
                Revision('d2', ('c2',)),

                Revision('mergeb3d2', ('b3', 'd2'))
            ]
        )

    def test_head_to_base(self):
        self._assert_iteration(
            "head", "base",
            [
                'b1a', 'a1a',
                'b1b', 'a1b',
                'mergeb3d2',
                    'b3', 'a3', 'base3',
                    'd2', 'c2', 'b2', 'a2', 'base2',
                'base1'
            ]
        )

    def test_head_to_base_exclusive(self):
        self._assert_iteration(
            "head", "base",
            [
                'b1a', 'a1a',
                'b1b', 'a1b',
                'mergeb3d2',
                    'b3', 'a3',
                    'd2', 'c2', 'b2', 'a2',
            ],
            inclusive=False
        )

    def test_head_to_blank(self):
        self._assert_iteration(
            "head", None,
            [
                'b1a', 'a1a',
                'b1b', 'a1b',
                'mergeb3d2',
                    'b3', 'a3', 'base3',
                    'd2', 'c2', 'b2', 'a2', 'base2',
                'base1'
            ]
        )

    def test_detect_invalid_base_selection(self):
        assert_raises_message(
            CommandError,
            "Requested base revision a2 overlaps with "
            "other requested base revisions",
            list,
            self.map._iterate_revisions(["c2"], ["a2", "b2"])
        )