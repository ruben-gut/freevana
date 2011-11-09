#!/usr/bin/env python
"""
Asorted utility functions
"""
__author__ = "RDG"

import re

def get_item_id(url):
    """
    Given a url, returns the item id
    """
    _id = 0
    parts = url.split("/", 3)
    if (len(parts) > 2):
        _id = parts[2]
    return _id

def remove_bom(text):
    """
    Removes the BOM from a string
    """
    return text.replace('\xef', '').replace('\xbb', '').replace('\xbf', '')

def titlecase(text):
    """
    Similar to string.title() but with some improvements.
    """
    return re.sub(r"[A-Za-z]+('[A-Za-z]+)?",
            lambda  mo: mo.group(0)[0].upper() +
                    mo.group(0)[1:].lower(),
            text)
