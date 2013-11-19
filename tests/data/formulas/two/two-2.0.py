from os.path import dirname

from ipkg.build import Formula, File


class two(Formula):

    name = 'two'
    version = '2.0'
    sources = File(dirname(__file__) + '/../../sources/two-1.0.tar.gz')
    platform = 'any'

    dependencies = ('four < 2.0', 'five')

    def install(self):
        pass
