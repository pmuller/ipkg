from os.path import dirname

from ipkg.build import Formula, File


class c(Formula):

    name = 'c'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/c-1.0.tar.gz')

    dependencies = ('d', 'e')

    def install(self):
        pass
