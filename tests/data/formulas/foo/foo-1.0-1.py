class foo(Formula):

    name = 'foo'
    version = '1.0'
    revision = 1
    sources = File('../../sources/foo-1.0.tar.gz')

    def install(self):
        self.run_cp(['README', self.environment.prefix])
