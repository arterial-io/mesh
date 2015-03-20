from setuptools import setup, find_packages

setup(
    name='mesh',
    version='2.0',
    description='A declarative API framework.',
    long_description=open('README.rst').read(),
    license='BSD',
    author='Jordan McCoy',
    author_email='mccoy.jordan@gmail.com',
    url='https://github.com/arterial-io/mesh',
    packages=find_packages(exclude=['docs', 'tests']),
    package_data={
        'mesh.binding': ['templates/*'],
        'mesh.doc': ['templates/*'],
    },
    keywords='data api framework',
    install_requires=[
        'scheme>=2',
        'bake>=2',
        'pyzmq>=14',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
