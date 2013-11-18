from os.path import dirname

from ipkg.build import Formula, File


class foobar(Formula):

    name = 'foo-bar'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/foo-bar-1.0.tar.bz2')
    dependencies = ('foo', 'bar')

    def install(self):
        self.run_cp(['README', self.environment.prefix + '/foo-bar.README'])
