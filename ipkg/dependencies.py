import logging
from collections import defaultdict

from .requirements import Requirement
from .exceptions import IpkgException
from .platforms import Platform
from .build import Formula
from .packages import MetaPackage
from . import versions


LOGGER = logging.getLogger(__name__)


def select_most_recent_version(objects):
    """Find the object having most recent version among ``objects``.
    """
    objects_by_version = {}
    for obj in objects:
        if isinstance(obj, Node):
            obj = obj.obj
        objects_by_version[obj.version] = obj
    most_recent_version = versions.most_recent(objects_by_version.keys())
    return objects_by_version[most_recent_version]


class SolverError(IpkgException):
    """An :py:class:`~Solver` error.
    """


class DependencyNotFound(SolverError):
    """Cannot find a satisfying package for a requirement.
    """
    def __init__(self, requirement, requirers):
        self.requirement = requirement
        self.requirers = requirers
        self.message = 'Cannot find package for requirement %s, required ' \
            'by %s' % (requirement, ', '.join(str(r) for r in requirers))


class DependencyLoop(SolverError):

    def __init__(self, target, sources):
        self.target = target
        self.sources = sources
        self.message = 'Dependency loop detected: %s still has dependents: ' \
            '%s' % (target, ', '.join(str(s) for s in sources))


class Node(object):
    """A node of a dependency :py:class:`~Solver`.

    :param obj: The node object
    :type obj: :py:class:`~ipkg.packages.PackageFile`, \
    :py:class:`~ipkg.packages.MetaPackage` or \
    :py:class:`~ipkg.build.Formula`
    """
    def __init__(self, obj, skip_dependencies=False):
        self.obj = obj
        # dict of Requirement: set of nodes who satisfy the requirement
        self.requirements = {}
        # list of nodes who depend on this one
        self.dependents = []

        if not skip_dependencies:
            for requirement_str in obj.dependencies:
                requirement = Requirement(requirement_str)
                self.requirements[requirement] = set()

    def __repr__(self):
        return 'Node(%r)' % self.obj

    @property
    def unsatisfied(self):
        """Returns the list of the node's unsatisfied requirements.
        """
        return [r for r, s in self.requirements.items() if not s]


class SolverRequirement(object):
    """A :class:`Solver` requirement.

    :param str name: Name of the required package.

    It merges requirements from multiple :class:`Node` objects.
    This object is used to find the best satisfying package.
    """
    def __init__(self, name):
        #: Package name
        self.name = name
        #: Merged :class:`Requirement`
        self.merged = Requirement(name)
        #: Dictionary of requesting :class:`Node`: node :class:`Requirement`
        self.requesters = {}
        #: ``set`` of satisfying :class:`Node` objects
        self.satisfiers = set()

    def merge(self, requirement, requester):
        """Merge with another requirement.

        :param requirement: requirement to merge with.
        :type requirement: ``str`` or :class:`Requirement`
        :param requester: requesting node
        :type requester: :class:`Node`
        """
        # Merge the requirement
        self.merged += requirement
        # Keep track of the requester and its original requirement
        self.requesters[requester] = requirement
        # remove satisfiers who no longer satisfy the merged
        # requirement
        satisfiers = []
        for satisfier in self.satisfiers:
            if self.merged.satisfied_by(satisfier.obj):
                satisfiers.append(satisfier)
        self.satisfiers = set(satisfiers)

    def satisfy(self, node):
        """Try to satisfy the requirement with a :class:`Node`.

        :rtype: Count of satisfied nodes.
        """
        satisfied = 0

        if self.merged.satisfied_by(node.obj):
            self.satisfiers.add(node)
            for requester, requester_req in self.requesters.items():
                requester.requirements[requester_req].add(node)
                node.dependents.append(requester)
                satisfied += 1

        return satisfied


class Solver(object):
    """The ipkg dependency solver.
    """
    def __init__(self):
        #: List of :class:`Node`
        self.nodes = []
        #: Dictionary of :class:`SolverRequirement`
        self.requirements = {}
        #: Dictionary using ``object`` as key and :class:`Node` as value
        self.objects = {}

    def add(self, obj, skip_dependencies=False):
        """Add a node to the solver.

        :type obj: :py:class:`~ipkg.packages.PackageFile`, \
        :py:class:`~ipkg.packages.MetaPackage` or \
        :py:class:`~ipkg.build.Formula`
        :param boolean skip_dependencies: Ignore object's requirements if \
        ``True``.

        When adding a node to the solver,
        it tries to match the new node to the unsatisfied
        requirements of the nodes already in the solver.
        """
        #LOGGER.debug('add %s', obj)
        if obj in self.objects:
            raise IpkgException('WTF: obj already in solver')

        new_node = Node(obj, skip_dependencies=skip_dependencies)

        # Merge the new node requirements to their corresponding
        # SolverRequirement objects
        for new_node_req in new_node.requirements:
            req_name = new_node_req.name
            if req_name not in self.requirements:
                self.requirements[req_name] = SolverRequirement(req_name)
            self.requirements[req_name].merge(new_node_req, new_node)

        # Try to satisfy other node requirements with this node
        if new_node.obj.name in self.requirements:
            self.requirements[new_node.obj.name].satisfy(new_node)

        self.nodes.append(new_node)
        self.objects[obj] = new_node

        return new_node

    @property
    def unsatisfied(self):
        """Returns a list of unsatisfied :class:`SolverRequirements`.
        """
        return [sr.merged for sr in self.requirements.values()
                if not sr.satisfiers]

    @classmethod
    def from_obj(cls, obj, environment=None, repositories=None):
        """Create a dependency solver from an ``obj``, which can be a
           ``Formula`` of a ``Package``.

        If an ``environment`` is given, it must be an
        ``ipkg.environments.Environent`` instance.
        All requirements satisfied by packages installed inside it are
        ignored (they are not added to the solver).

        if ``repositories`` is given, it must be an iterable of
        ``ipkg.repositories.FormulaRepository`` or
        ``ipkg.repositories.PackageRepository`` instances.
        They can be mixed.
        """

        solver = cls()
        node = solver.add(obj)
        queue = set()

        for requirement in node.requirements:
            queue.add((node, requirement))

        while queue:
            requiring_node, requirement = queue.pop()
            LOGGER.debug('Current: %r %r', requiring_node, requirement)

            if requirement.name in solver.requirements:
                LOGGER.debug('Requirement %s exists in solver: satisfiers=%r',
                             requirement.name,
                             solver.requirements[requirement.name].satisfiers)
                if solver.requirements[requirement.name].satisfiers:
                    LOGGER.debug('Satisfied requirement %s satisfied in solver',
                                 requirement)
                    requirement_node_set = solver.requirements[requirement.name].satisfiers.copy()
                    requiring_node.requirements[requirement] = requirement_node_set
                    for requirement_node in requirement_node_set:
                        requirement_node.dependents.append(requiring_node)
                    continue
#                else:
#                    LOGGER.debug('Requirement %s not satisfied by %r',
#                                 requirement,
#                                 solver.requirements[requirement.name])

            if environment:
                found = False
                for package in environment.packages:
                    if requirement.satisfied_by(package):
                        LOGGER.debug('Satisfied by environment package %s',
                                     package)
                        solver.add(package)
                        found = True
                        break
                if found is True:
                    continue

            for repository in repositories or []:
                satisfiers = repository.find(requirement)

                for satisfier in satisfiers:
                    LOGGER.debug('Satisfied by %s found in %s',
                                 satisfiers, repository)
                    new_node = solver.add(satisfier)
                    for satisfier_req in new_node.requirements:
                        queue.add((new_node, satisfier_req))

        return solver

    def __from_target(self, target):
        if isinstance(target, Node):
            if target in self.nodes:
                return target
            else:
                raise IpkgException('Unknown target: %r' % target)
        else:
            if target in self.objects:
                return self.objects[target]
            else:
                raise IpkgException('Unknown target: %r' % target)

    def find_best_dependencies(self, target,
                               dependency_selector=select_most_recent_version):
        target = self.__from_target(target)
        req_queue = []
        dependencies = {}

        for t_req in target.requirements:
            req_queue.append((target, self.requirements[t_req.name].merged))

        while req_queue:
            cr_owner, cur_req = req_queue.pop(0)
            cr_name = cur_req.name

            if cr_name in dependencies:
                continue

            if cr_name not in self.requirements:
                raise IpkgException('Requirement not found: %s, asked by %s' %
                                    (cur_req, cr_owner))

            solver_req = self.requirements[cr_name]

            if not solver_req.satisfiers:
                raise IpkgException('No satisfier found for requirement %s, '
                                    'asked by %s' % (cur_req, cr_owner))

            satisfier = dependency_selector(solver_req.satisfiers)

            for satisfier_req in self.objects[satisfier].requirements:
                req_queue.append((satisfier, satisfier_req))

            dependencies[satisfier.name] = satisfier

        return dependencies.values()

    def solve(self, target=None, dependency_selector=select_most_recent_version,
              ignore_installed_packages=True):
        """Returns a list of nodes sorted by their mutual dependencies.

        If ``target`` is defined, only target and its dependencies will be
        used.

        ``dependency_selector`` should be a callable which takes an iterable
        of ``Node`` and returns the preferred one.

        If ``ignore_installed_packages`` is true (the default),
        the installed packages will be removed from the list.
        """
        sorted_nodes = []
        queue = []

        LOGGER.debug('All nodes: %r', self.nodes)
        LOGGER.debug('Requirements: %r', self.requirements)

        if target is None:
            nodes = self.nodes
        else:
            target = self.__from_target(target)
            nodes = [target]
            for obj in self.find_best_dependencies(target, dependency_selector):
                nodes.append(self.objects[obj])

        for node in nodes:
            LOGGER.debug('node %r', node)
            if not node.dependents:
                queue.append(node)
        LOGGER.debug('Queue: %r', queue)

        if not queue:
            raise IpkgException('Cannot find a node which is not a '
                                'dependency of other nodes (loop?)')

        node_dependents = {}

        while queue:
            node = queue.pop(0)
            LOGGER.debug('Node from queue: %r', node)
            sorted_nodes.append(node)

            for requirement in node.requirements:
                node_set = self.requirements[requirement.name].satisfiers
                LOGGER.debug(' Available nodes for requirement %s: %s',
                             requirement, node_set)

                node_set_len = len(node_set)
                if node_set_len == 0:
                    raise IpkgException('Unsatisfied requirement: %s, '
                                        'asked by %s' % (requirement, node))
                elif node_set_len == 1:
                    dependency = list(node_set)[0]
                else:
                    dependency = self.objects[dependency_selector(node_set)]

                LOGGER.debug(' Best satisfier for requirement %s: %s (%i)',
                             requirement, dependency, id(dependency))

                if dependency not in node_dependents:
                    node_dependents[dependency] = set(dependency.dependents)
                    LOGGER.debug(' First time we see %s, dependents=%s',
                                 dependency, node_dependents[dependency])

                for dependent in list(node_dependents[dependency]):
                    if dependent.obj.name == node.obj.name:
                        node_dependents[dependency].remove(dependent)
                LOGGER.debug(' %s dependents: %s',
                             dependency, node_dependents[dependency])

                if not node_dependents[dependency]:
                    # no other node depend on the dependency
                    LOGGER.debug(' Added %s to queue', dependency)
                    queue.append(dependency)
                else:
                    LOGGER.debug(' %s not added to queue', dependency)
            
            LOGGER.debug('queue %r', queue)
            LOGGER.debug('sorted_nodes %r', sorted_nodes)

        for node, dependents in node_dependents.items():
            if dependents:
                raise DependencyLoop(node, dependents)

        result = []
        for node in reversed(sorted_nodes):
            if ignore_installed_packages:
                if not isinstance(node.obj, MetaPackage):
                    result.append(node.obj)
            else:
                result.append(node.obj)

        return result
