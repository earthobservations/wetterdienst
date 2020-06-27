from setuptools import setup, find_packages
from python_dwd.version import __version__

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='python_dwd',
    version=__version__,
    description='A module for accessing data of the german weather service',
    license='MIT',
    long_description=long_description,
    author='Benjamin Gutzmann, Daniel Lassahn, Andreas Motl',
    author_email='gutzemann@gmail.com',
    packages=find_packages(),
    install_requires=[
        "pandas",
        "tables",
        "numpy",
        "scipy",
        "h5py",
        "cachetools",
        "aiofiles",
        "ipython",
        "ipython-genutils",
        "matplotlib",
        "pytest",
        "mock",
        "fire",
        "docopt",
        "munch",
        "dateparser",
        "fire",
        "requests",
        "beautifulsoup4"
    ],
    entry_points={
        'console_scripts': [
            'dwd = python_dwd.cli:run',
        ]
    },
)
