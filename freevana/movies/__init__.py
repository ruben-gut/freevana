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
movie_id INTEGER, source TEXT, definition TEXT, audio TEXT, url TEXT);

"""

# Not used for now:

# CREATE TABLE movies_metadata (id INTEGER, name TEXT, alt_name TEXT, 
# director TEXT, year INTEGER, category TEXT, lang TEXT);

# system
import os
import re
import sys
import json
import time
# third party
import mechanize
from BeautifulSoup import BeautifulSoup
# own
import freevana
from freevana.utils import get_item_id, titlecase, remove_bom

MEDIA_LIST_URL = 'http://www.cuevana.tv/web/peliculas?&todas'
MEDIA_PATTERN = '\$\(\'#list\'\)\.list\(\{l:\[(.*)\], page'

MEDIA_SOURCES_URL_PATTERN = '%s%s' % ('http://www.cuevana.tv/player/sources',
                                                    '?id=%s&tipo=pelicula')
SUBTITLES_LOCATION = './subtitles/movies'
SUBTITLES_URL_PATTERN = 'http://sc.cuevana.tv/files/sub/%s_%s.srt'

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
        self.no_sources_movies = []

    def update_movie_list(self):
        """
        Download the list of movies and saves them to the DB
        """
        print "***** Starting to list movies... *****"

        # Don't run this if we're already done
        if (self.finished_listing_movies):
            print "All movie pages already processed... skipping..."
            return

        # Obtain list of movies
        data = self.browser.open(MEDIA_LIST_URL)
        soup = BeautifulSoup(data.read())
        script_data = soup.find('script')

        all_movies = []
        match = re.search(MEDIA_PATTERN, str(script_data))
        if (match):
            series_json = '[%s]' % match.group(1)
            all_movies = json.loads(series_json)

        for movie in all_movies:
            print "Adding Movie ID %s, Name: %s" % (movie['id'],
                                                movie['tit'])
            self.add_movie(movie)

        self.finished_listing_movies = True

    def add_movie(self, movie):
        """
        Given a movie data, add it to the database
        """
        if self._movie_exists(movie['id']):
            print ">> Movie already in database: %s" % movie['tit']
            return
        else:
            print "Adding movie: %s" % movie['tit']

        data = (movie['id'], movie['tit'].strip(), movie['tit'].strip(),
                movie['url'], 0, 0)
        query  = 'INSERT INTO movies (id, name, alt_name, url, subs, sources)'
        query += ' VALUES (?, ?, ?, ?, ?, ?)'
        try:
            self.execute_query(query, data)
        except Exception, ex:
            print "Could not add movie #%s, %s, because: %s" % (movie['id'],
                                                    movie['tit'].strip(), ex)
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
        print "***** Start updating sources... *****"
        try:
            query = 'SELECT id, name FROM movies WHERE sources=0 ORDER BY id'
            movies = self.run_query(query, as_list=True)

            print "NO SOURCES: %s" % self.no_sources_movies
            for movie in movies:
                (movie_id, movie_name) = movie
                if (movie_id not in self.no_sources_movies):
                    url  = MEDIA_SOURCES_URL_PATTERN % movie_id
                    print "Sources for #%s %s" % (movie_id, movie_name)
                    data = self.browser.open(url)
                    source_data = self.get_sources(BeautifulSoup(data.read()))
                    if (source_data):
                        count = self.handle_sources(source_data, 'pelicula',
                                            url, movie_id, self.save_source)
                        # don't mark srcs as downloaded if we had none
                        if (count > 0):
                            self.mark_sources_as_downloaded(movie_id)
                    else:
                        self.no_sources_movies.append(movie_id)

                    time.sleep(freevana.REQUEST_SLEEP_TIME)
                else:
                    print "Movie had no sources: %s" % movie_name
        except Exception, ex:
            print "Coudln't update sources: %s" % ex
            raise ex # propagate exception

    def save_source(self, movie_id, source, definition, audio, url):
        """
        Save source information into the DB.
        """
        try:
            query  = 'INSERT INTO movie_sources '
            query += '(movie_id, source, definition, audio, url) VALUES '
            query += '(?, ?, ?, ?, ?)'
            data = (movie_id, source, definition, audio, url)
            self.execute_query(query, data)
            print "Added source for Movie ID: %s, Source: %s, Link: %s" % (
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
                    if (not self._subtitle_exists(movie_id, lang)):
                        print "Downloading subs for #%s - %s in %s" % (
                                                movie_id, movie_name, lang)
                        self.download_subtitle(movie_id, lang)
                        time.sleep(freevana.SUBTITLES_SLEEP_TIME)
                self.mark_subs_as_downloaded(movie_id)
        except Exception, ex:
            print "Could not download subtitles: %s" % ex
            raise ex # propagate the exception

    def _subtitle_exists(self, movie_id, lang):
        """
        Check if a subtitle already exists
        """
        filename = "%s/%s_%s.srt" % ( "%s/%s" % (SUBTITLES_LOCATION, lang),
                                                        movie_id, lang)
        return os.path.exists(filename)

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