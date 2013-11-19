from os.path import dirname

from ipkg.build import Formula, File


class d(Formula):

    name = 'd'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/d-1.0.tar.gz')
    platform = 'any'

    def install(self):
        pass
