from setuptools import setup

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='python_dwd',
    version="1.0.0",
    description='A module for accessing data of the german weather service',
    license='MIT',
    long_description=long_description,
    author='Benjamin Gutzmann',
    author_email='gutzemann@gmail.com',
    packages=['python_dwd'],  # , 'python_dwd.additionals'
    install_requires=['pandas', 'pathlib',
                      'scipy', 'numpy'],
    entry_points={
        'console_scripts': [
            'dwd = python_dwd.cli:run',
        ]
    },
)
