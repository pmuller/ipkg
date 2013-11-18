from os.path import dirname

from ipkg.build import Formula, File


class e(Formula):

    name = 'e'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/e-1.0.tar.gz')

    dependencies = ('d',)

    def install(self):
        pass
