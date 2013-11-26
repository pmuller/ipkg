from os.path import dirname

from ipkg.build import Formula, File


class four(Formula):

    name = 'four'
    version = '1.8'
    sources = File(dirname(__file__) + '/../../sources/four-1.0.tar.gz')
    platform = 'any'

    def install(self):
        pass
