from os.path import dirname

from ipkg.build import Formula, File


class a(Formula):

    name = 'a'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/a-1.0.tar.gz')

    dependencies = ('b', 'c')

    def install(self):
        pass
