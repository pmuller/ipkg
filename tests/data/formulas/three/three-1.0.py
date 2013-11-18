from os.path import dirname

from ipkg.build import Formula, File


class three(Formula):

    name = 'three'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/three-1.0.tar.gz')

    def install(self):
        pass
