#!/usr/bin/env python
"""
Freevana main package
"""
__author__ = "Tirino"

"""
CREATE TABLE database_version (id INTEGER PRIMARY KEY, version TEXT);
"""

# system
import urllib
import sqlite3
import cookielib
import traceback
import sys
# third party
import mechanize

HTTP_USER_AGENT = "%s%s%s" % ('Mozilla/5.0 (Macintosh; U; Intel ',
                        'Mac OS X 10_6_6; en-us) AppleWebKit/533.19.4 ',
                        '(KHTML, like Gecko) Version/5.0.3 Safari/533.19.4')
HTTP_ACCEPT_LANGUAGE = 'en-us;q=0.7,en;q=0.3'
HTTP_GENERIC_ERROR = 'HTTP Error'

HTTP_FILE_NOT_FOUND = '404'
HTTP_SERVER_ERRORS = ['503', '502', '501', '500']

class TemporaryErrorException(Exception):
    """
    Raised when the remote server is having temporary problems
    Usually when it returns Error 503.
    """
    pass

class FileNotFoundException(Exception):
    """
    Raised when a file is not found on the remote server.
    """
    pass

def parse_exception(ex, data):
    """
    Take a generic exception and tries to return one that says
    more about the error, such as "FileNotFoundException".
    """
    result = ex
    error_msg = str(ex)
    if HTTP_GENERIC_ERROR in error_msg:
        if HTTP_FILE_NOT_FOUND in error_msg:
            result = FileNotFoundException("File Not Found: %s" % data)
        else:
            for error_number in HTTP_SERVER_ERRORS:
                if error_number in error_msg:
                    result = TemporaryErrorException("Server error: %s" % ex)
    return result

DB_FILE_LOCATION = './db/freevana.db'

MEDIA_DATA_HOST = 'http://www.cuevana.tv'
SUBTITLES_LANGUAGES = ['ES', 'EN', 'PT']

MEDIA_MOVIES_PATH = '/peliculas/lista/'
MEDIA_MOVIES_PATTERN = r'\/peliculas\/[0-9]'

SUBTITLES_MOVIES_LOCATION = './subtitles/movies'
SUBTITLES_MOVIES_URL_PATTERN = 'http://sc.cuevana.tv/files/sub/%s_%s.srt'

SUBTITLES_SERIES_LOCATION = './subtitles/series'
SUBTITLES_SERIES_URL_PATTERN = 'http://sc.cuevana.tv/files/sub/%s_%s.srt'

class Freevana(object):
    """
    Handle connecting to the remote media server and doing
    generic stuff. Meant to be subclassed.
    """
    def __init__(self):
        """
        Initialize DB access and browser support
        """
        # Init DB
        self.conn = sqlite3.connect(DB_FILE_LOCATION)
        self.conn.text_factory = str
        # Init Browser
        self.browser = mechanize.Browser()
        self.browser.addheaders = [('User-Agent', HTTP_USER_AGENT),
                                ('Accept-Language', HTTP_ACCEPT_LANGUAGE)]
        self.browser.set_handle_robots(False)
        # Enable Cookies
        self.cookie_jar = cookielib.LWPCookieJar()
        self.browser.set_cookiejar(self.cookie_jar)

    def run_query(self, query, values=None, as_list=False):
        """
        Run a SELECT query and returns the results.
        If "as_list" is set to True, iterate the cursor's content internally
        and return a list with the data instead of the cursor.
        """
        result = None
        cursor = self.conn.cursor()
        try:
            if (values):
                cursor.execute(query, values)
            else:
                cursor.execute(query)
            if (as_list):
                result = cursor.fetchall()
            else:
                result = cursor
        except KeyboardInterrupt, ex: # let's catch it just in case
            print ex
            sys.exit(0)
        except Exception, ex:
            raise ex
        finally:
            if cursor:
                cursor.close()
        return result

    def execute_query(self, query, values=None):
        """
        Run an INSERT/UPDATE or DELETE query and returns whatever the server
        returns.
        """
        result = None
        cursor = self.conn.cursor()
        try:
            if (values):
                result = cursor.execute(query, values)
            else:
                result = cursor.execute(query)
            # Save (commit) the changes
            self.conn.commit()
        except KeyboardInterrupt, ex: # let's catch it just in case
            print ex
            sys.exit(0)
        except Exception, ex:
            raise ex
        finally:
            if cursor:
                cursor.close()
        return result

    def ajax_request(self, url, params, referer=None):
        """
        Simulate an ajax request
        """
        # Do an Ajax call simulating the browser
        # User mechanize.Request to send POST request
        req = mechanize.Request(url, urllib.urlencode(params))
        req.add_header('User-Agent', HTTP_USER_AGENT)
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        req.add_header('Content-Type', 
                        'application/x-www-form-urlencoded; charset=UTF-8')
        if (referer):
            req.add_header('Referer', referer)
        # Use the same cookie jar we've been using
        self.cookie_jar.add_cookie_header(req)
        result = mechanize.urlopen(req)
        return result.read()
