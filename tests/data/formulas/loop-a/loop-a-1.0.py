from os.path import dirname

from ipkg.build import Formula, File


class loop_a(Formula):

    name = 'loop-a'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/loop-a-1.0.tar.gz')

    dependencies = ('loop-b', 'loop-c')

    def install(self):
        pass
