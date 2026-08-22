"""
The active intelligence section: a prompt read into a map, images observed without it, and the
two brought together afterwards.

DELIBERATELY EMPTY OF IMPORTS. Several lanes land modules in this package in the same wave, and a
package `__init__` that re-exported them would be the one file all of those branches had to edit.
Import the modules directly:

    from backend.services.inquiry_intelligence import intent, observer, observation_audit
"""
