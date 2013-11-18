from os.path import dirname

from ipkg.build import Formula, File


class two(Formula):

    name = 'two'
    version = '1.5'
    sources = File(dirname(__file__) + '/../../sources/two-1.0.tar.gz')

    dependencies = ('four < 2.0', 'five')

    def install(self):
        pass
