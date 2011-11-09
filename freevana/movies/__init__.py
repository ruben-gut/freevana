#!/usr/bin/env python
"""
Freevana Movies
"""
__author__ = "Tirino"

# pylint: disable-msg=W0105

# Movies tables
"""
CREATE TABLE movies (id INTEGER PRIMARY KEY, name TEXT, alt_name TEXT, 
url TEXT, subs INTEGER, sources INTEGER);

CREATE TABLE movie_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, 
movie_id INTEGER, source TEXT, source_id TEXT, url TEXT);
"""

# Not used for now:

# CREATE TABLE movies_metadata (id INTEGER, name TEXT, alt_name TEXT, 
# director TEXT, year INTEGER, category TEXT, lang TEXT);

# system
import re
import sys
# third party
import mechanize
from BeautifulSoup import BeautifulSoup
# own
import freevana
from freevana.utils import get_item_id, titlecase, remove_bom

MEDIA_LIST_URL = 'http://www.cuevana.tv/peliculas/lista/'
MEDIA_PATTERN = r'\/peliculas\/[0-9]'

MEDIA_SOURCES_URL_PATTERN = '%s%s' % ('http://www.cuevana.tv/player/source',
                                    '?id=%s&subs=,ES&onstart=yes&sub_pre=ES')
MEDIA_SOURCE_URL = 'http://www.cuevana.tv/player/source_get'
MEDIA_SOURCE_PATTERN = "goSource\('([A-Za-z0-9_]*)','([A-Za-z0-9_]*)'\)"

SUBTITLES_LOCATION = './subtitles/movies'
SUBTITLES_URL_PATTERN = 'http://sc.cuevana.tv/files/sub/%s_%s.srt'

SKIP_IMG_TEXT = '[IMG]'

# pylint: disable-msg=W0703
class MoviesUpdater(freevana.Freevana):
    """
    Class for updating the freevana movies database.
    """
    def __init__(self):
        freevana.Freevana.__init__(self)
        self.current_page = 1
        self.last_page = 0
        self.finished_listing_movies = False

    def update_movie_list(self):
        """
        Download the list of movies and saves them to the DB
        """
        print "***** Starting to list movies... *****"

        # Don't run this if we're already done
        if (self.finished_listing_movies):
            print "All movie pages already processed... skipping..."
            return

        # Get the current last page if not already set
        if (self.last_page == 0):
            self.last_page = self.get_last_page()

        if (self.last_page == 0):
            raise Exception("Couldn't obtain a valid 'last page'!")
        else:
            print "Last Page is: %s" % self.last_page

        # Iterate movie pages
        try:
            url = None
            for this_page in xrange(self.current_page, self.last_page + 1):
                self.current_page = this_page
                print "Processing Page #%s" % this_page
                url = "%spage=%s" % (MEDIA_LIST_URL, this_page)
                self.browser.open(url)
                for link in self.browser.links(url_regex=MEDIA_PATTERN):
                    if (link.text != SKIP_IMG_TEXT): # skip img links
                        self.add_movie(link)
                if (self.current_page == self.last_page):
                    self.finished_listing_movies = True
        except Exception, ex:
            new_ex = freevana.parse_exception(ex, url)
            if (isinstance(new_ex, freevana.FileNotFoundException)):
                # this one is ok to happen, we guess (for now)
                print new_ex
            else:
                raise new_ex # propagate the exception

    def get_last_page(self):
        """
        Get the current last page of movies
        """
        last_page = 0
        try:
            self.browser.open(MEDIA_LIST_URL)
            # find all links with urls containing 'page='
            for link in self.browser.links(url_regex=r'page='):
                if link.text != '':
                    try:
                        page = int(link.text)
                        if page > last_page:
                            last_page = page
                    except Exception, ex:
                        print "Couldn't parse text: %s, Exception: %s" % (
                                                                link.text, ex)
        except Exception, ex:
            new_ex = freevana.parse_exception(ex, MEDIA_LIST_URL)
            if (isinstance(new_ex, freevana.FileNotFoundException)):
                # this one is ok to happen, we guess (for now)
                print new_ex
            else:
                raise new_ex # propagate the exception
        return last_page

    def add_movie(self, link):
        """
        Given a movie Link object, add it to the database
        """
        movie_id = get_item_id(link.url)

        if self._movie_exists(movie_id):
            print ">> Movie already downloaded: %s" % link.text
            return
        else:
            print "Adding movie: %s" % link.text

        alt_name = get_movie_name(link.url)
        data = (movie_id, link.text, alt_name, link.url, 0, 0)
        query  = 'INSERT INTO movies (id, name, alt_name, url, subs, sources) '
        query += 'VALUES (?, ?, ?, ?, ?, ?)'
        try:
            self.execute_query(query, data)
        except Exception, ex:
            print "Could not add movie #%s, %s, because: %s" % (movie_id,
                                                            link.text, ex)
            raise ex # propagate the exception

    def _movie_exists(self, movie_id):
        """
        Check if a movie already exists in the DB
        """
        try:
            query = 'SELECT id FROM movies WHERE id=%s LIMIT 1' % movie_id
            result = self.run_query(query, as_list=True)
            return (len(result) > 0)
        except Exception, ex:
            print "Couldn't check if the movie exists: %s" % ex
            raise ex # propagate the exception


    def process_sources(self):
        """
        Iterate the list of movies from the DB and get the
        sources of those that don't have them yet
        """
        print "***** Start downloading sources... *****"
        try:
            query = 'SELECT id, name FROM movies WHERE sources=0'
            movies = self.run_query(query, as_list=True)

            for movie in movies:
                (movie_id, movie_name) = movie
                url  = MEDIA_SOURCES_URL_PATTERN % movie_id
                print "Sources for #%s %s" % (movie_id, movie_name)
                data = self.browser.open(url)
                sources = self.get_sources(BeautifulSoup(data.read()))
                count = 0
                for source in sources:
                    source_id = sources[source]
                    print "Source: %s, SourceId: %s" % (source, source_id)
                    link = self.get_download_link(source, source_id, url)
                    if (link):
                        self.save_source(movie_id, source, source_id, link)
                        count = count + 1
                    else:
                        raise Exception("Couldn't get link for %s => %s" % (
                                                            movie_id, source))
                if (count > 0): # don't mark srcs as downloaded if we had none
                    self.mark_sources_as_downloaded(movie_id)
        except Exception, ex:
            print "Coudln't download sources: %s" % ex
            raise ex # propagate exception

    def get_sources(self, soup):
        """
        Get the available sources for a specific movie
        """
        sources = {}
        for script in soup.findAll(name='script'):
            match = re.search(MEDIA_SOURCE_PATTERN, str(script))
            if match and match.group(2): # some sources may come without names!
                sources[match.group(2)] = match.group(1)
        return sources

    def get_download_link(self, source, source_id, referrer):
        """
        Obtain the download link for the specified source
        """
        source_params = {'key': source_id, 'host': source, 'vars':''}
        result = self.ajax_request(MEDIA_SOURCE_URL, source_params, referrer)
        return remove_bom(result.strip())

    def save_source(self, movie_id, source, source_id, url):
        """
        Save source information into the DB.
        """
        try:
            query  = 'INSERT INTO movie_sources '
            query += '(movie_id, source, source_id, url) VALUES (?, ?, ?, ?)'
            data = (movie_id, source, source_id, url)
            self.execute_query(query, data)
            print "Added source for MovieID: %s, Source: %s, Link: %s" % (
                                                        movie_id, source, url)
        except Exception, ex:
            print "Couldn't save the source: %s" % ex
            raise ex # propagate the exception

    def mark_sources_as_downloaded(self, movie_id):
        """
        Update the DB marking the movie sources as 'downloaded'.
        """
        try:
            query = 'UPDATE movies SET sources=1 WHERE id=%s' % movie_id
            self.execute_query(query)
        except Exception, ex:
            print "Couldn't mark sources as downloaded: %s" % ex
            raise ex


    def download_subtitles(self):
        """
        Download the subtitles for all movies that need it.
        """
        print "***** Start downloading subtitles... *****"
        try:
            query = 'SELECT id, name FROM movies WHERE subs=0'
            movies = self.run_query(query, as_list=True)
            for movie in movies:
                (movie_id, movie_name) = movie
                for lang in freevana.SUBTITLES_LANGUAGES:
                    print "Downloading subs for #%s - %s in %s" % (movie_id,
                                                            movie_name, lang)
                    self.download_subtitle(movie_id, lang)
                self.mark_subs_as_downloaded(movie_id)
        except Exception, ex:
            print "Could not download subtitles: %s" % ex
            raise ex # propagate the exception

    def download_subtitle(self, movie_id, lang):
        """
        Download a Subtitle in a specific language
        """
        try:
            url = SUBTITLES_URL_PATTERN % (movie_id, lang)
            self.browser.retrieve(url, filename="%s/%s_%s.srt" % (
                            "%s/%s" % (SUBTITLES_LOCATION, lang),
                            movie_id, lang))
        except KeyboardInterrupt, ex:
            print ex
            sys.exit(0)
        except Exception, ex:
            new_ex = freevana.parse_exception(ex, url)
            if (isinstance(new_ex, freevana.FileNotFoundException)):
                # this one is ok to happen, we guess (for now)
                print 'No subtitle in %s. %s' % (lang, new_ex)
            else:
                raise new_ex # propagate the exception

    def mark_subs_as_downloaded(self, movie_id):
        """
        Update the DB marking the movie's subs as downloaded.
        """
        try:
            query = 'UPDATE movies SET subs=1 WHERE id=%s' % movie_id
            self.execute_query(query)
        except Exception, ex:
            print "Couldn't mark subs as downloaded: %s" % ex
            raise ex # propagate the exception


def get_movie_name(url):
    """
    Get the (alternative) movie name from the URL
    """
    name = url
    parts = url.rsplit("/", 2)
    if (len(parts) > 1):
        name = titlecase(parts[1].replace("-", " "))
    return name