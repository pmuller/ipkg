from unittest import TestCase
from shutil import rmtree
from tempfile import mkdtemp
from os.path import join, dirname

from ipkg.dependencies import Solver, Node, DependencyNotFound, \
    select_most_recent_version, DependencyLoop
from ipkg.repositories import LocalPackageRepository, FormulaRepository
from ipkg.build import Formula
from ipkg.environments import Environment


DATA_DIR = join(dirname(__file__), 'data')
PACKAGE_DIR = join(DATA_DIR, 'packages')
FORMULA_DIR = join(DATA_DIR, 'formulas')


class TestNode(TestCase):

    def test_unsatisfied(self):
        formula = Formula.from_file(join(FORMULA_DIR,
                                         'foo-bar/foo-bar-1.0.py'))
        node = Node(formula)
        unsatisfied = sorted(r.name for r in node.unsatisfied)
        self.assertEqual(unsatisfied, ['bar', 'foo'])


class TestSolver(TestCase):

    def test_add(self):
        solver = Solver()
        foobar = Formula.from_file(join(FORMULA_DIR,
                                   'foo-bar/foo-bar-1.0.py'))
        solver.add(foobar)

        foo = Formula.from_file(join(FORMULA_DIR,
                                'foo/foo-1.0.py'))
        solver.add(foo)

        self.assertEqual(len(solver.nodes), 2)
        self.assertEqual(len(solver.unsatisfied), 1)

    def test_from_obj(self):
        foo = Formula.from_file(join(FORMULA_DIR,
                                'foo/foo-1.0.py'))
        solver = Solver.from_obj(foo)

    def test_from_obj__unsatisfied_dependencies(self):
        foobar = Formula.from_file(join(FORMULA_DIR,
                                   'foo-bar/foo-bar-1.0.py'))
        solver = Solver.from_obj(foobar)
        self.assertEqual(len(solver.unsatisfied), 2)

    def test_from_obj__environment(self):
        tmpdir = mkdtemp()
        prefix = join(tmpdir, 'env')
        environment = Environment(prefix)
        environment.directories.create()
        environment.install(join(PACKAGE_DIR,
                                 'foo/foo-1.0-1-any.ipkg'))
        foobar = Formula.from_file(join(FORMULA_DIR,
                                   'foo-bar/foo-bar-1.0.py'))
        solver = Solver.from_obj(foobar, environment)
        self.assertEqual(len(solver.unsatisfied), 1)
        rmtree(tmpdir)

    def test_from_obj__repository_package(self):
        repository = LocalPackageRepository(PACKAGE_DIR)
        foobar = Formula.from_file(join(FORMULA_DIR,
                                   'foo-bar/foo-bar-1.0.py'))
        solver = Solver.from_obj(foobar, repositories=[repository])
        self.assertEqual(len(solver.unsatisfied), 0)

    def test_from_obj__repository_formula(self):
        repository = FormulaRepository(FORMULA_DIR)
        foobar = Formula.from_file(join(FORMULA_DIR,
                                   'foo-bar/foo-bar-1.0.py'))
        solver = Solver.from_obj(foobar, repositories=[repository])
        self.assertEqual(len(solver.unsatisfied), 0)

    def test_find_best_dependencies__foo_bar(self):
        repository = FormulaRepository(FORMULA_DIR)
        foobar = Formula.from_file(join(FORMULA_DIR,
                                   'foo-bar/foo-bar-1.0.py'))
        solver = Solver.from_obj(foobar, repositories=[repository])
        self.assertEqual(
            [(o.name, o.version) for o in solver.find_best_dependencies(foobar)],
            [('foo', '1.0'), ('bar', '1.0')])

    def test_find_best_dependencies__abcde(self):
        repository = FormulaRepository(FORMULA_DIR)
        a = Formula.from_file(join(FORMULA_DIR, 'a/a-1.0.py'))
        solver = Solver.from_obj(a, repositories=[repository])
        self.assertEqual(
            [(o.name, o.version) for o in solver.find_best_dependencies(a)],
            [('c', '1.0'), ('b', '1.0'), ('e', '1.0'), ('d', '1.0')])

    def test_find_best_dependencies__numbers(self):
        repository = FormulaRepository(FORMULA_DIR)
        one = Formula.from_file(join(FORMULA_DIR, 'one/one-1.0.py'))
        solver = Solver.from_obj(one, repositories=[repository])
        self.assertEqual(
            [(o.name, o.version) for o in solver.find_best_dependencies(one)],
            [('four', '1.8'), ('five', '1.0'), ('two', '1.6'), ('three', '2.0')])

    def test_solve__abcde(self):
        repository = FormulaRepository(FORMULA_DIR)
        a = Formula.from_file(join(FORMULA_DIR, 'a/a-1.0.py'))
        solver = Solver.from_obj(a, repositories=[repository])
        order = solver.solve(a)
#        self.assertEqual(
#            [obj.name for obj in order],
#            ['d', 'e', 'c', 'b', 'a'])
#        self.assertEqual(
#            [obj.name for obj in order],
#            ['d','b','e','c','a'])
        self.assertEqual(
            [obj.name for obj in order],
            ['d', 'e', 'b', 'c', 'a'])

    def test_solve__numbers(self):
        repository = FormulaRepository(FORMULA_DIR)
        one = Formula.from_file(join(FORMULA_DIR, 'one/one-1.0.py'))
        solver = Solver.from_obj(one, repositories=[repository])
        order = solver.solve(one)
        self.assertEqual(
            [(obj.name, obj.version) for obj in order],
            [('four', '1.8'), ('five', '1.0'), ('three', '2.0'), ('two', '1.6'), ('one', '1.0')])

    def test_solve__loop(self):
        repository = FormulaRepository(FORMULA_DIR)
        loop_a = Formula.from_file(join(FORMULA_DIR, 'loop-a/loop-a-1.0.py'))
        solver = Solver.from_obj(loop_a, repositories=[repository])
#        for node in solver.nodes:
#            print node
#            for req in node.requirements.items():
#                print '\t', req
#        import pprint
#        pprint.pprint(solver.requirements)
        self.assertRaises(DependencyLoop, solver.solve, loop_a)


class TestSelectMostRecentVersion(TestCase):

    def test(self):
        two_1_0 = Formula.from_file(join(FORMULA_DIR, 'two/two-1.0.py'))
        two_1_5 = Formula.from_file(join(FORMULA_DIR, 'two/two-1.5.py'))
        two_1_6 = Formula.from_file(join(FORMULA_DIR, 'two/two-1.6.py'))
        two_2_0 = Formula.from_file(join(FORMULA_DIR, 'two/two-2.0.py'))
        self.assertEqual(select_most_recent_version([two_1_5, two_1_0, two_2_0,
                                                     two_1_6]), two_2_0)
