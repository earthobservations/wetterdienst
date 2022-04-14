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

import sphinx_material
import tomlkit

sys.path.insert(0, os.path.abspath(".."))


# https://github.com/wemake-services/wemake-python-styleguide/blob/master/docs/conf.py#L22-L37
def _get_project_meta():
    with open("../pyproject.toml") as pyproject:
        file_contents = pyproject.read()

    return tomlkit.parse(file_contents)["tool"]["poetry"]


# -- Project information -----------------------------------------------------
pkg_meta = _get_project_meta()

project = str(pkg_meta["name"])
copyright = "Copyright (c) 2018-2020 earthobservations"
author = str(pkg_meta["authors"])
version = str(pkg_meta["version"])

# -- General configuration ---------------------------------------------------

master_doc = "index"

# latex_engine = 'xelatex'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.imgconverter",
    #"sphinxcontrib.rsvgconverter",
    "sphinx_autodoc_typehints",
    "matplotlib.sphinxext.plot_directive",
    "IPython.sphinxext.ipython_directive",
    "IPython.sphinxext.ipython_console_highlighting",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]


# -- Custom options -------------------------------------------------

todo_include_todos = True


# -- Autodoc options -------------------------------------------------

# This value contains a list of modules to be mocked up. This is useful when
# some external dependencies are not met at build time and break the building process.
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#confval-autodoc_mock_imports
# autodoc_mock_imports = [
#     "pandas",
#     "numpy",
#     "scipy",
#     "dateutil",
#     "dateparser",
# ]

# Use docstring from both class-level and __init__ when documenting a class.
autoclass_content = "both"


# -- Material options -------------------------------------------

html_show_sourcelink = True
html_sidebars = {
    "**": ["logo-text.html", "globaltoc.html", "localtoc.html", "searchbox.html"]
}

# Required theme setup
extensions.append("sphinx_material")
html_theme = "sphinx_material"
html_theme_path = sphinx_material.html_theme_path()
html_context = sphinx_material.get_html_context()

# Material theme options (see theme.conf for more information)
html_theme_options = {
    # Set the name of the project to appear in the navigation.
    "nav_title": "Wetterdienst",
    # Set you GA account ID to enable tracking
    #'google_analytics_account': 'UA-XXXXX',
    # Specify a base_url used to generate sitemap.xml. If not
    # specified, then no sitemap will be built.
    "base_url": "https://wetterdienst.readthedocs.io/",
    # Set the color and the accent color
    #'color_primary': 'blue',
    #'color_primary': 'blue-grey',
    #'color_primary': 'indigo',
    "color_primary": "light-blue",
    # 'color_accent': 'light-green',
    # Set the repo location to get a badge with stats
    "repo_url": "https://github.com/earthobservations/wetterdienst",
    "repo_name": "wetterdienst",
    # Visible levels of the global TOC; -1 means unlimited
    "globaltoc_depth": 2,
    # If False, expand all TOC entries
    #'globaltoc_collapse': False,
    # If True, show hidden TOC entries
    #'globaltoc_includehidden': False,
    "master_doc": False,
    "nav_links": [],
    "heroes": {
        # "index": "Open weather data for humans.",
        "pages/cli": "On your fingertips.",
    },
}
