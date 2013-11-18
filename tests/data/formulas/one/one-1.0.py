from os.path import dirname

from ipkg.build import Formula, File


class one(Formula):

    name = 'one'
    version = '1.0'
    sources = File(dirname(__file__) + '/../../sources/one-1.0.tar.gz')

    dependencies = ('two>1,<2', 'three==2.0')

    def install(self):
        pass
