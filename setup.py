from setuptools import setup

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='pydwd',
    version=0.1,
    description='A module for accessing data from german weather service',
    license='MIT',
    long_description=long_description,
    author='Benjamin Gutzmann',
    author_email='gutzemann@gmail.com',
    packages=['pydwd'],
    install_requires=['pandas']
)
