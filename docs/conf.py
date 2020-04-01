# Sphinx configuration
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import datetime
import importlib
import inspect
import re
import subprocess
import sys
from typing import Optional

from invoke_release.version import __version__


print(sys.path)

_year = datetime.date.today().year
_date = datetime.datetime.utcnow().strftime('%Y %B %d %H:%M UTC')

project = 'Invoke Release'
# noinspection PyCompatibility
copyright = f'{_year}, Eventbrite'
author = 'Eventbrite'
version = __version__
release = __version__

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.linkcode',
]
source_suffix = {
    '.rst': 'restructuredtext',
}
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

source_encoding = 'utf-8-sig'
master_doc = 'index'
# noinspection PyCompatibility
rst_epilog = f"""
Copyright © {_year} Eventbrite, freely licensed under `Apache License, Version 2.0
<https://www.apache.org/licenses/LICENSE-2.0>`_.

Documentation generated {_date}.
"""
primary_domain = 'py'
add_function_parentheses = True
add_module_names = True
language = 'en'

html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'related_projects.html',
        'searchbox.html',
    ],
}

html_favicon = None  # TODO
html_short_title = 'Invoke release'
html_static_path = ['_static']
html_theme = 'alabaster'
html_theme_options = {
    'fixed_sidebar': True,
    'github_button': True,
    'github_repo': 'invoke-release',
    'github_user': 'eventbrite',
}
html_title = 'Invoke Release - Easy Python Releases'
html_use_index = True

autodoc_default_options = {
    'exclude-members': '__weakref__, __attrs_attrs__, __attrs_post_init__, __dict__, __slots__, __module__, __eq__, '
                       '__ne__, __ge__, __gt__, __le__, __lt__, __hash__, __repr__, __abstractmethods__, '
                       '__orig_bases__, __parameters__, __annotations__',
    'members': True,
    'show-inheritance': True,
    'special-members': True,
    'undoc-members': True,
}
autodoc_inherit_docstrings = True
autodoc_member_order = 'alphabetical'
autodoc_typehints = 'signature'


def linkcode_resolve(domain, info):
    if domain != 'py' or not info['module']:
        return None

    source_re = re.compile(rf'.*((site|dist)-packages|invoke-release)/invoke_release')

    try:
        commit: Optional[str] = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('utf-8').strip()
    except subprocess.CalledProcessError:
        commit = None

    module = importlib.import_module(info['module'])
    file_name = module.__file__
    source_path = source_re.sub('invoke_release', file_name)
    where = f'blob/{commit}' if commit else f'tree/{__version__}'
    suffix = ''

    attr = None
    if '.' in info['fullname']:
        obj_names = info['fullname'].split('.')
        attr = module
        obj = getattr(module, obj_names[0])
        for obj_name in obj_names:
            attr = getattr(attr, obj_name)
    else:
        obj = getattr(module, info['fullname'])

    try:
        source, start_line = inspect.getsourcelines(attr if attr else obj)
        if not (source and start_line) or start_line == 1:
            source, start_line = inspect.getsourcelines(obj)
    except (TypeError, OSError):
        try:
            source, start_line = inspect.getsourcelines(obj)
        except (TypeError, OSError):
            source, start_line = [], 0
    if source and start_line:
        suffix = f'#L{start_line}-L{start_line + len(source) - 1}'

    return (
        f'https://github.com/eventbrite/invoke-release/{where}/{source_path}{suffix}'
    )
