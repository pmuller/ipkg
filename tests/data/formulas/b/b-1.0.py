from os.path import dirname

from ipkg.build import Formula, File


class b(Formula):

    name = 'b'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/b-1.0.tar.gz')
    platform = 'any'

    dependencies = ['d']

    def install(self):
        pass
