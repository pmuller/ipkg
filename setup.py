#!/usr/bin/env python

from setuptools import setup, find_packages


setup(
    name='ipkg',
    version='0.8.0',
    description='Simple package management',
    author='Philippe Muller',
    url='http://ipkg.org',
    packages=find_packages(),
    install_requires=('requests>=2.0.0',),
    entry_points="""

        [console_scripts]
        ipkg = ipkg.cli:ipkg

        [setuptools.installation]
        eggsecutable = ipkg.cli:ipkg

        [ipkg.vfiles.backend]
        file=ipkg.vfiles.backends:LocalFile
        http=ipkg.vfiles.backends:HttpFile
        https=ipkg.vfiles.backends:HttpFile
    """,
)
