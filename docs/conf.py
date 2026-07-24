# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
# Read metadata from the installed package so this works on any supported Python
# version (tomllib is only available on 3.11+, while the project supports 3.10+).
from importlib.metadata import metadata

_meta = metadata("wetterdienst")

project = _meta["Name"]
copyright = "earthobservations"
author = _meta["Author"]
version = _meta["Version"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
master_doc = "index"

latex_engine = "xelatex"

extensions = [
    "myst_nb",
    "autodoc2",
    "sphinx_copybutton",
]

# -- MyST / MyST-NB configuration --------------------------------------------
# https://myst-parser.readthedocs.io/en/latest/syntax/optional.html
myst_enable_extensions = [
    "attrs_block",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "substitution",
    "tasklist",
]
# Generate anchor slugs for headings up to level 3 so pages can be cross-linked.
myst_heading_anchors = 3

# Execute notebook-style pages at build time and give remote data cells enough
# time to fetch from the upstream weather services (default is 30s).
nb_execution_timeout = 120
nb_execution_show_tb = True

autodoc2_packages = [
    {
        "path": "../src/wetterdienst",
    }
]

# Providers re-export their `*Metadata` objects, so autodoc2's static analysis
# sees the same object under two module paths. These duplicates are harmless.
suppress_warnings = ["autodoc2.dup_item"]

# -- sphinx-copybutton -------------------------------------------------------
# Strip interactive prompts (>>>, ..., $) so copied snippets are runnable.
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

templates_path = ['_templates']
# autodoc2 writes a full auto-generated tree to "apidocs"; the documented API is
# curated inline via {autodoc2-object} in library/*.md, so keep the generated
# tree out of the build to avoid orphaned/duplicate-object warnings.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'apidocs']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_theme = 'sphinx_book_theme'
html_theme_options = {
    "path_to_docs": "/docs",
    "repository_url": "https://github.com/earthobservations/wetterdienst",
    "use_edit_page_button": True,
    "use_repository_button": True,
    "use_issues_button": True,
    "use_download_button": True,
    "use_fullscreen_button": True,
    "max_navbar_depth": 5
}
html_title = "Wetterdienst Documentation"
