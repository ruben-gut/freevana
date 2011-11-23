#!/usr/bin/env python
"""
Freevana main package
"""
__author__ = "Tirino"

"""
CREATE TABLE database_version (id INTEGER PRIMARY KEY, 
version TEXT, release_date TEXT);
"""

# system
import re
import urllib
import sqlite3
import cookielib
import json
import traceback
import sys
# third party
import mechanize
# own
from freevana.utils import remove_bom

DATABASE_VERSION = '1.1'

HTTP_USER_AGENT = "%s%s%s" % ('Mozilla/5.0 (Macintosh; U; Intel ',
                        'Mac OS X 10_6_6; en-us) AppleWebKit/533.19.4 ',
                        '(KHTML, like Gecko) Version/5.0.3 Safari/533.19.4')
HTTP_ACCEPT_LANGUAGE = 'en-us;q=0.7,en;q=0.3'
HTTP_GENERIC_ERROR = 'HTTP Error'

HTTP_FILE_NOT_FOUND = '404'
HTTP_SERVER_ERRORS = ['503', '502', '501', '500']

REQUEST_SLEEP_TIME = 0.3
SUBTITLES_SLEEP_TIME = 0.2

SUPPORTED_LANGS = {1:u'Espa\xf1ol', 2:u'Ingl\xe9s', 3:u'Portugu\xe9s', 
                4:u'Alem\xe1n', 5:u'Franc\xe9s', 6:u'Coreano', 7:u'Italiano',
                8:u'Tailand\xe9s', 9:u'Ruso', 10:u'Mongol', 11:u'Polaco', 
                12:u'Esloveno', 13:u'Sueco', 14:u'Griego', 15:u'Canton\xe9s', 
                16:u'Japon\xe9s', 17:u'Dan\xe9s', 18:u'Neerland\xe9s', 
                19:u'Hebreo', 20:u'Serbio', 21:u'\xc1rabe', 22:u'Hindi', 
                23:u'Noruego', 24:u'Turco', 26:u'Mandar\xedn', 
                27:u'Nepal\xe9s', 28:u'Rumano', 29:u'Iran\xed',30:u'Est\xf3n',
                31:u'Bosnio', 32:u'Checo', 33:u'Croata', 34:u'Fin\xe9s', 
                35:u'H\xfanagro'}

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

MEDIA_SOURCE_URL = 'http://www.cuevana.tv/player/source_get'
MEDIA_SOURCE_PATTERN = "sources = (.*), sel_source"

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
        self.check_db_version()
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
        returns and the insertid in a tuple.
        """
        result = (None, None)
        exec_result = None
        cursor = self.conn.cursor()
        try:
            if (values):
                exec_result = cursor.execute(query, values)
            else:
                exec_result = cursor.execute(query)
            # Save (commit) the changes
            self.conn.commit()
            result = (exec_result, cursor.lastrowid)
        except KeyboardInterrupt, ex: # let's catch it just in case
            print ex
            sys.exit(0)
        except Exception, ex:
            raise ex
        finally:
            if cursor:
                cursor.close()
        return result

    def check_db_version(self):
        """
        Check if the current user database can be used with this version of
        Freevana.
        """
        result = False
        user_db_version = None
        rows = self.run_query("SELECT version FROM database_version",
                                                        as_list=True)
        if (rows and len(rows) > 0):
            user_db_version = rows[0][0]
            if (user_db_version == DATABASE_VERSION):
                result = True

        if (not result):
            print 'Invalid database version. You may need an updated version'
            print 'Your version: %s, Expected version: %s' % (user_db_version,
                                                            DATABASE_VERSION)
            sys.exit(0)

        return result

    def get_sources(self, soup):
        """
        Get the available sources for a specific item
        """
        sources = {}
        for script in soup.findAll(name='script'):
            match = re.search(MEDIA_SOURCE_PATTERN, str(script))
            if match and match.group(1):
                sources = json.loads(match.group(1))
                if (not isinstance(sources, dict)):
                    print "Looks like this item has no sources: %s" % (
                                                                    sources)
                    sources = {}
        return sources

    def handle_sources(self, source_data, kind, url, item_id, save_func):
        """
        Process all different available sources
        """
        count = 0
        for definition in source_data.keys():
            sources = source_data[definition]
            for audio in sources.keys():
                for source in sources[audio]:
                    # don't process empty sources
                    if (source):
                        print "Source: %s, Audio: %s" % (source, audio)
                        
                        link = self.get_download_link(item_id, kind, 
                            MEDIA_SOURCE_URL, source, definition, audio, url)

                        if (link):
                            save_func(item_id, source, definition, audio, link)
                            count = count + 1
                        else:
                            raise Exception(
                                "Couldn't get link for %s => %s" % (
                                                item_id, source))
        return count


    def get_download_link(self, item_id, kind, source_url, source, definition,
                          audio, referer):
        """
        Obtain the download link for the specified source
        """
        source_params = {'id':item_id, 'def':definition, 'audio':audio, 
                         'host':source, 'tipo':kind}
        result = self.ajax_request(source_url, source_params, referer)
        result = urllib.unquote(result).replace('play2?megaurl=', '')
        match = re.search('(.*)&id', result)
        if (match and match.group(1)):
            result = match.group(1)
        return remove_bom(result.strip())

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
