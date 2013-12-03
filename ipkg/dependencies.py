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
    pass


class DependencyNotFound(SolverError):

    MESSAGE = 'Cannot find requirement %s, required by %s'


class DependencyLoop(SolverError):

    MESSAGE = 'Dependency loop detected between %s and its dependents: %s'


class Node(object):
    """A node of a dependency ``Graph``.

    ``obj`` can be a package or a formula.
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


class Graph(object):
    """The ipkg dependency solver.
    """
    def __init__(self):
        self.nodes = []  # list of nodes
        self.requirements = {}  # requirement name: dict
        self.objects = {}  # object: node

    def add(self, obj, skip_dependencies=False):
        """Add a node to the graph.

        ``obj`` can be a ``Formula`` or a ``Package`` object.

        If ``skip_dependencies`` is true,
        objects dependencies are ignored.

        When adding a node to the graph,
        we try to match the new node to the unsatisfied requirements of
        the nodes already in the graph.
        """
        #LOGGER.debug('add %s', obj)
        if obj in self.objects:
            raise IpkgException('WTF: obj already in graph')

        new_node = Node(obj, skip_dependencies=skip_dependencies)

        #LOGGER.debug('inspecting new node requirements')
        for new_node_req in new_node.requirements:
            #LOGGER.debug('new_node_req %s', new_node_req)
            if new_node_req.name in self.requirements:
                cur_req = self.requirements[new_node_req.name]['requirement']
                new_req = cur_req + new_node_req
                req_d = self.requirements[new_node_req.name]
                req_d['requirement'] = new_req
                req_d['requesters'][new_node] = new_node_req
                # remove satisfiers who no longer satisfy the merged
                # requirement
                satisfiers = []
                for satisfier in req_d['satisfiers']:
                    if new_req.satisfied_by(satisfier.obj):
                        satisfiers.append(satisfier)
                req_d['satisfiers'] = set(satisfiers)
            else:
                #LOGGER.debug('has not %s', new_node_req.name)
                self.requirements[new_node_req.name] = {
                    'requirement': new_node_req,
                    'requesters': {new_node: new_node_req},
                    'satisfiers': set(),
                }

        # Try to satisfy other node requirements with this node
        if new_node.obj.name in self.requirements:
            req_d = self.requirements[new_node.obj.name]
            if req_d['requirement'].satisfied_by(new_node.obj):
                req_d['satisfiers'].add(new_node)
                LOGGER.debug('req_d %r', req_d)
                for requester, requester_req in req_d['requesters'].items():
                    requester.requirements[requester_req].add(new_node)
                    new_node.dependents.append(requester)
                    LOGGER.debug('%s requirement %s satisfied by %s',
                                 requester, requester_req, new_node)

        self.nodes.append(new_node)
        self.objects[obj] = new_node

        return new_node

    @property
    def unsatisfied(self):
        """Returns a list of unsatisfied ``Requirements``.
        """
        return [d['requirement'] for d in self.requirements.values()
                if not d['satisfiers']]

    @classmethod
    def from_obj(cls, obj, environment=None, repositories=None):
        """Create a dependency graph from an ``obj``, which can be a
           ``Formula`` of a ``Package``.

        If an ``environment`` is given, it must be an
        ``ipkg.environments.Environent`` instance.
        All requirements satisfied by packages installed inside it are
        ignored (they are not added to the graph).

        if ``repositories`` is given, it must be an iterable of
        ``ipkg.repositories.FormulaRepository`` or
        ``ipkg.repositories.PackageRepository`` instances.
        They can be mixed.
        """

        graph = cls()
        node = graph.add(obj)
        queue = set()

        for requirement in node.requirements:
            queue.add((node, requirement))

        while queue:
            requiring_node, requirement = queue.pop()
            LOGGER.debug('Current: %r %r', requiring_node, requirement)

            if requirement.name in graph.requirements:
                LOGGER.debug('Requirement %s exists in graph: satisfiers=%r',
                             requirement.name,
                             graph.requirements[requirement.name]['satisfiers'])
                if graph.requirements[requirement.name]['satisfiers']:
                    LOGGER.debug('Satisfied requirement %s satisfied in graph',
                                 requirement)
                    requirement_node_set = graph.requirements[requirement.name]['satisfiers'].copy()
                    requiring_node.requirements[requirement] = requirement_node_set
                    for requirement_node in requirement_node_set:
                        requirement_node.dependents.append(requiring_node)
                    continue
#                else:
#                    LOGGER.debug('Requirement %s not satisfied by %r',
#                                 requirement,
#                                 graph.requirements[requirement.name])

            if environment:
                found = False
                for package in environment.packages:
                    if requirement.satisfied_by(package):
                        LOGGER.debug('Satisfied by environment package %s',
                                     package)
                        graph.add(package)
                        found = True
                        break
                if found is True:
                    continue

            for repository in repositories or []:
                satisfiers = repository.find(requirement)

                for satisfier in satisfiers:
                    LOGGER.debug('Satisfied by %s found in %s',
                                 satisfiers, repository)
                    new_node = graph.add(satisfier)
                    for satisfier_req in new_node.requirements:
                        queue.add((new_node, satisfier_req))

        return graph

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
            req_d = self.requirements[t_req.name]
            req_queue.append((target, req_d['requirement']))

        while req_queue:
            cur_req_owner, cur_req = req_queue.pop(0)

            if cur_req.name in dependencies:
                continue

            if cur_req.name not in self.requirements:
                raise IpkgException('Requirement not found: %s, asked by %s' %
                                    (cur_req, cur_req_owner))

            req_d = self.requirements[cur_req.name]

            if not req_d['satisfiers']:
                raise IpkgException('No satisfier found for requirement %s, '
                                    'asked by %s' % (cur_req, cur_req_owner))

            satisfier = dependency_selector(req_d['satisfiers'])

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
                node_set = self.requirements[requirement.name]['satisfiers']
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
