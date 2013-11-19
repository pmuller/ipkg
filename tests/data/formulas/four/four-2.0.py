from os.path import dirname

from ipkg.build import Formula, File


class four(Formula):

    name = 'four'
    version = '2.0'
    sources = File(dirname(__file__) + '/../../sources/four-1.0.tar.gz')
    platform = 'any'

    def install(self):
        pass
