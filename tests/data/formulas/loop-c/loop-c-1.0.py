from os.path import dirname

from ipkg.build import Formula, File


class loop_c(Formula):

    name = 'loop-c'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/loop-c-1.0.tar.gz')

    dependencies = ('loop-b',)

    def install(self):
        pass
