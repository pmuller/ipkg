#!/usr/bin/env python

from setuptools import setup, find_packages


setup(
    name='ipkg',
    version='0.10.0',
    description='Package management for humans',
    author='Philippe Muller',
    url='http://ipkg.org',
    license='MIT',
    packages=find_packages(),
    install_requires=('requests>=2.0.0',),
    entry_points="""

        [console_scripts]
        ipkg = ipkg.cli:ipkg

        [setuptools.installation]
        eggsecutable = ipkg.cli:ipkg

        [ipkg.files.backend]
        file=ipkg.files.backends.filesystem:LocalFile
        http=ipkg.files.backends.http:HttpFile
        https=ipkg.files.backends.http:HttpFile
    """,
    classifiers=(
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development',
        'Topic :: System :: Installation/Setup',
        'Topic :: System :: Software Distribution',
        'Topic :: Utilities',
    ),
)
