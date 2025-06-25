# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import tomllib

with open("../pyproject.toml", "rb") as f:
    data = tomllib.load(f)["project"]
    
project = data["name"]
copyright = "earthobservations"
author = ", ".join(author["name"] for author in data["authors"])
version = str(data["version"])

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
master_doc = "index"

latex_engine = "xelatex"

extensions = [
    "myst_nb",
    "autodoc2",
    'sphinx_copybutton',
]

autodoc2_packages = [
    {
        "path": "../wetterdienst",
    }
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

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
