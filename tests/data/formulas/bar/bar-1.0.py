from os.path import dirname

from ipkg.build import Formula, File


class bar(Formula):

    name = 'bar'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/bar-1.0.tar.bz2')
    platform = 'any'

    def install(self):
        self.run_cp(['README', self.environment.prefix + '/bar.README'])
