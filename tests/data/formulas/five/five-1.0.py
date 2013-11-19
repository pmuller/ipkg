from os.path import dirname

from ipkg.build import Formula, File


class five(Formula):

    name = 'five'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/five-1.0.tar.gz')
    platform = 'any'

    dependencies = ('four > 1.0',)

    def install(self):
        pass
