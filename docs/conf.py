# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'wetterdienst'
copyright = '2025, Benjamin Gutzmann, Andreas Motl'
author = 'Benjamin Gutzmann, Andreas Motl'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
master_doc = "index"
extensions = [
    "myst_nb",
    "autodoc2",
]

autodoc2_packages = [
    {
        "path": "../wetterdienst",
        # "auto_mode": True,  # auto-regenerates docs during sphinx-build
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
    "use_repository_button": True,
    "use_issues_button": True,
    "use_download_button": True,
    "use_fullscreen_button": True,
    "home_page_in_toc": True,
    "max_navbar_depth": 5
}
html_title = "Wetterdienst Documentation"

html_static_path = ['_static']
