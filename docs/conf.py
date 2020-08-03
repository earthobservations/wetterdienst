# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#

# Check https://github.com/wemake-services/wemake-python-styleguide/blob/master/docs/conf.py#L22-L37
# for how to get the version from the pyproject.toml
import os
import sys
import tomlkit
sys.path.insert(0, os.path.abspath('..'))


# https://github.com/wemake-services/wemake-python-styleguide/blob/master/docs/conf.py#L22-L37
def _get_project_meta():
    with open('../pyproject.toml') as pyproject:
        file_contents = pyproject.read()

    return tomlkit.parse(file_contents)['tool']['poetry']


# -- Project information -----------------------------------------------------
pkg_meta = _get_project_meta()

project = str(pkg_meta['name'])
copyright = '2020, earthobservations including Benjamin Gutzmann, Daniel Lassahn, Andreas Motl'
author = 'Benjamin Gutzmann, Daniel Lassahn, Andreas Motl'

# The full version, including alpha/beta/rc tags
version = str(pkg_meta['version'])

release = version


# -- General configuration ---------------------------------------------------

master_doc = 'index'

# latex_engine = 'xelatex'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx_rtd_theme",
    "sphinx.ext.autosectionlabel",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
