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

sys.path.insert(0, os.path.abspath(".."))


# https://github.com/wemake-services/wemake-python-styleguide/blob/master/docs/conf.py#L22-L37
def _get_project_meta():
    with open("../pyproject.toml") as pyproject:
        file_contents = pyproject.read()

    return tomlkit.parse(file_contents)["project"]


# -- Project information -----------------------------------------------------
pkg_meta = _get_project_meta()

project = str(pkg_meta["name"])
copyright = "Copyright (C) 2018-2023 earthobservations"  # noqa: A001
author = ", ".join(author["name"] for author in pkg_meta["authors"])
version = str(pkg_meta["version"])

# -- General configuration ---------------------------------------------------

master_doc = "index"

latex_engine = "xelatex"

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.imgconverter",
    "sphinxcontrib.rsvgconverter",
    "sphinx_autodoc_typehints",
    "matplotlib.sphinxext.plot_directive",
    "IPython.sphinxext.ipython_directive",
    "IPython.sphinxext.ipython_console_highlighting",
    "sphinx_design",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
html_show_sourcelink = True

html_theme = "furo"

html_static_path = ["_static"]

# theme options
html_theme_options = {
    "navigation_with_keys": True,
}

# -- Custom options -------------------------------------------------

todo_include_todos = True

# Use docstring from both class-level and __init__ when documenting a class.
autoclass_content = "both"
