from os.path import dirname

from ipkg.build import Formula, File


class loop_b(Formula):

    name = 'loop-b'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/loop-b-1.0.tar.gz')
    platform = 'any'

    dependencies = ('loop-c',)

    def install(self):
        pass
