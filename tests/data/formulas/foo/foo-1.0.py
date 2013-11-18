from os.path import dirname

from ipkg.build import Formula, File


class foo(Formula):

    name = 'foo'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/foo-1.0.tar.gz')

    def install(self):
        self.run_cp(['README', self.environment.prefix + '/foo.README'])
