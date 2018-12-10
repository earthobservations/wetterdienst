from setuptools import setup, find_packages
from pydwd import __version__

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='pydwd',
    version=__version__,
    description='A module for accessing data from german weather service',
    license='MIT',
    long_description=long_description,
    author='Benjamin Gutzmann',
    author_email='gutzemann@gmail.com',
    packages=find_packages(),
    install_requires=['pandas']
)
