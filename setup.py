from setuptools import setup

from python_dwd import __version__

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='python_dwd',
    version=__version__,
    description='A module for accessing data of the german weather service',
    license='MIT',
    long_description=long_description,
    author='Benjamin Gutzmann',
    author_email='gutzemann@gmail.com',
    packages=['python_dwd'],  # , 'python_dwd.additionals'
    install_requires=['pandas', 'tqdm', 'pathlib', 'zipfile']
)
