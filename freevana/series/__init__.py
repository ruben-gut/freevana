#!/usr/bin/env python
"""
Freevana Series
"""
__author__ = "Tirino"

# pylint: disable-msg=W0105

# Series tables
"""
CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT);

CREATE TABLE series_seasons (id INTEGER PRIMARY KEY, 
series_id INTEGER, number INTEGER, name TEXT, finished INTEGER);

CREATE TABLE series_episodes (id INTEGER PRIMARY KEY, season_id INTEGER, 
number TEXT, short_name TEXT, name TEXT, subs INTEGER, sources INTEGER);

CREATE TABLE series_episode_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, 
series_episode_id INTEGER, source TEXT, source_id TEXT, url TEXT);
"""

# system
import re
import sys
# third party
import mechanize
from BeautifulSoup import BeautifulSoup
# own
import freevana
from freevana.utils import get_item_id, titlecase, remove_bom

MEDIA_LIST_URL = 'http://www.cuevana.tv/series/'
MEDIA_PATTERN = r'\/series\/[0-9]'

SEASONS_URL_PATTERN = 'http://www.cuevana.tv/list_search_id.php?serie=%s'

EPISODES_URL_PATTERN = 'http://www.cuevana.tv/list_search_id.php?temporada=%s'

MEDIA_SOURCES_URL_PATTERN = '%s%s' % ('http://www.cuevana.tv/player/source',
                            '?id=%s&subs=,ES&onstart=yes&tipo=s&sub_pre=ES')

MEDIA_SOURCE_URL = 'http://www.cuevana.tv/player/source_get'
MEDIA_SOURCE_PATTERN = "goSource\('([A-Za-z0-9_]*)','([A-Za-z0-9_]*)'\)"

SUBTITLES_LOCATION = './subtitles/series'
SUBTITLES_URL_PATTERN = 'http://sc.cuevana.tv/files/s/sub/%s_%s.srt'

SKIP_IMG_TEXT = '[IMG]'

# pylint: disable-msg=W0703
class SeriesUpdater(freevana.Freevana):
    """
    Class for updating the freevana series database.
    """
    def __init__(self):
        freevana.Freevana.__init__(self)
        self.finished_listing_series = False
        self.finished_listing_seasons = False
        self.finished_listing_episodes = False

    def update_series_list(self):
        """
        Download the list of series and saves them to the DB
        """
        if (self.finished_listing_series):
            print "All current series already processed... skipping..."
            return

        print "***** Starting to list series... *****"

        # Obtain list of series
        data = self.browser.open(MEDIA_LIST_URL)
        soup = BeautifulSoup(data.read())
        series_ul = soup.find('ul', attrs={'id':'serie'})
        all_series = series_ul.findAll('script')

        for series in all_series:
            # Remove un wanted parts
            series = str(series).replace('<script type="text/javascript">',
                                                '').replace('</script>', '')
            series = series.replace('serieslist.push(', '').replace(');', 
                                                                '').strip()
            series = series.replace('{id', '{"id"').replace(',nombre',
                                                            ',"name"')
            series = eval(series)
            print "Adding Series ID %s, Name: %s" % (series['id'],
                                                    series['name'])
            self.add_series(series)

        self.finished_listing_series = True

    def add_series(self, series):
        """
        Given a series data, add it to the database
        """
        if self._series_exists(series['id']):
            print ">> Series already added: %s" % series['name']
            return

        data = (series['id'], series['name'])
        query  = 'INSERT INTO series (id, name) VALUES (?, ?)'
        try:
            self.execute_query(query, data)
        except Exception, ex:
            print "Could not add #%s, %s, because: %s" % (series['id'],
                                                        series['name'], ex)
            raise ex # propagate the exception

    def _series_exists(self, series_id):
        """
        Check if a series already exists in the DB
        """
        try:
            query = 'SELECT id FROM series WHERE id=%s LIMIT 1' % series_id
            result = self.run_query(query, as_list=True)
            return (len(result) > 0)
        except Exception, ex:
            print "Couldn't check if the series exists: %s" % ex
            raise ex # propagate the exception

    def update_seasons(self):
        """
        Update the list of seasons for all series
        """
        if (self.finished_listing_seasons):
            print "All current seasons already processed... skipping..."
            return

        print "***** Start updating seasons... *****"
        try:
            query = 'SELECT id, name FROM series'
            all_series = self.run_query(query, as_list=True)
            for series in all_series:
                (series_id, series_name) = series
                url = SEASONS_URL_PATTERN % series_id
                print "Seasons for #%s %s" % (series_id, series_name)

                data = self.browser.open(url)
                soup = BeautifulSoup(data.read())
                seasons = soup.findAll('li')
                self.add_seasons(series_id, seasons)

            self.finished_listing_seasons = True
        except Exception, ex:
            print "Could not download season: %s" % ex
            raise ex # propagate the exception

    def add_seasons(self, series_id, seasons):
        """
        Given a list of seasons, add each of them to the DB
        """
        try:
            number = 1
            for season in seasons:
                content = str(season)
                match = re.search('\"[0-9].*\"', content)
                season_id = int(match.group(0).replace('"', ''))
                match = re.search('>[A-Za-z0-9].*<', content)
                season_name = match.group(0).replace('>', 
                                                '').replace('<','')
                print "Adding Season ID %s, Name: %s" % (season_id, 
                                                        season_name)
                self.add_season(series_id, season_id, number,
                                                    season_name)
                number = number + 1
        except Exception, ex:
            print "Could not add seasons: %s" % ex
            raise ex # propagate the exception

    def add_season(self, series_id, season_id, number, season_name):
        """
        Add a season to the DB
        """
        if self._season_exists(series_id, season_id):
            print ">> Season already added: %s" % season_name
            return

        data = (season_id, series_id, number, season_name, 0)
        query  = 'INSERT INTO series_seasons '
        query += '(id, series_id, number, name, finished)'
        query += 'VALUES (?, ?, ?, ?, ?)'
        try:
            self.execute_query(query, data)
        except Exception, ex:
            print "Could not add season #%s, %s, because: %s" % (season_id,
                                                            season_name, ex)
            raise ex # propagate the exception

    def _season_exists(self, series_id, season_id):
        """
        Check if a series already exists in the DB
        """
        try:
            query  = 'SELECT id FROM series_seasons '
            query += 'WHERE id=? AND series_id=? LIMIT 1'
            result = self.run_query(query, (season_id, series_id),
                                                        as_list=True)
            return (len(result) > 0)
        except Exception, ex:
            print "Couldn't check if the season exists: %s" % ex
            raise ex # propagate the exception

    def update_episodes(self):
        """
        Update the list of seasons for all series
        """
        if (self.finished_listing_episodes):
            print "All current episodes already processed... skipping..."
            return

        print "***** Start updating episodes... *****"
        try:
            query  = 'SELECT DISTINCT ss.id, ss.name, s.name as series_name '
            query += 'FROM series_seasons ss '
            query += 'INNER JOIN series s ON (ss.series_id=s.id) '
            query += 'WHERE ss.finished=0 ORDER BY s.id ASC, ss.number ASC'
            seasons = self.run_query(query, as_list=True)
            for season in seasons:
                (season_id, season_name, series_name) = season
                url = EPISODES_URL_PATTERN % season_id
                print "Episodes for %s => #%s %s" % (series_name, season_id,
                                                                season_name)
                data = self.browser.open(url)
                soup = BeautifulSoup(data.read())
                episodes = soup.findAll('li')
                self.add_episodes(season_id, episodes)

            self.finished_listing_episodes = True
        except Exception, ex:
            print "Could not download episode: %s" % ex
            raise ex # propagate the exception

    def add_episodes(self, season_id, episodes):
        """
        Given a list of episodes, add each of them to the DB.
        """
        try:
            for episode in episodes:
                content = str(episode)
                # Episode ID
                match = re.search(r',\"[0-9].*\"\)', content)
                episode_id = int(match.group(0).replace(',"', 
                                                    '').replace('")', ''))
                # Episode Number
                match = re.search(r'nume\">[0-9].*<\/span', content)
                number = match.group(0).replace('nume">', 
                                        '').replace('</span', '').strip()
                # Episode Name
                match = re.search(r'span> [^<].*<', content)
                episode_name = match.group(0).replace('span> ', 
                                            '').replace('<','').strip()
                print "Adding Episode ID %s, Nbr: %s Name: %s" % (
                                        episode_id, number, episode_name)
                self.add_episode(season_id, episode_id, number, 
                                                    episode_name)
        except Exception, ex:
            print "Could not add episodes: %s" % ex
            raise ex # propagate the exception

    def add_episode(self, season_id, episode_id, number, episode_name):
        """
        Add an episode to the DB
        """
        if self._episode_exists(season_id, episode_id):
            print ">> Episode already added: %s" % episode_name
            return

        data = (episode_id, season_id, number, episode_name, '', 0, 0)
        query  = 'INSERT INTO series_episodes '
        query += '(id, season_id, number, short_name, name, subs, sources)'
        query += 'VALUES (?, ?, ?, ?, ?, ?, ?)'
        try:
            self.execute_query(query, data)
        except Exception, ex:
            print "Could not add episode #%s, %s, because: %s" % (episode_id,
                                                            episode_name, ex)
            raise ex # propagate the exception

    def _episode_exists(self, season_id, episode_id):
        """
        Check if a series already exists in the DB
        """
        try:
            query  = 'SELECT id FROM series_episodes '
            query += 'WHERE season_id=? AND id=?'
            result = self.run_query(query, (season_id, episode_id),
                                                        as_list=True)
            return (len(result) > 0)
        except Exception, ex:
            print "Couldn't check if the episode exists: %s" % ex
            raise ex # propagate the exception


    def process_sources(self):
        """
        Iterate the list of episodes from the DB and get the
        sources of those that don't have them yet
        """
        print "***** Start downloading sources... *****"
        try:
            query  = 'SELECT id, short_name FROM series_episodes '
            query += 'WHERE sources=0'
            episodes = self.run_query(query, as_list=True)

            for episode in episodes:
                (episode_id, episode_name) = episode
                url  = MEDIA_SOURCES_URL_PATTERN % episode_id
                print "Sources for #%s %s" % (episode_id, episode_name)
                data = self.browser.open(url)
                sources = self.get_sources(BeautifulSoup(data.read()))
                for source in sources:
                    source_id = sources[source]
                    print "Source: %s, SourceId: %s" % (source, source_id)
                    link = self.get_download_link(source, source_id, url)
                    if (link):
                        self.save_source(episode_id, source, source_id, link)
                    else:
                        raise Exception("Couldn't get link for %s => %s" % (
                                                        episode_id, source))
                self.mark_sources_as_downloaded(episode_id)
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

    def save_source(self, episode_id, source, source_id, url):
        """
        Save source information into the DB.
        """
        try:
            query  = 'INSERT INTO series_episode_sources '
            query += '(series_episode_id, source, source_id, url) '
            query += 'VALUES (?, ?, ?, ?)'
            data = (episode_id, source, source_id, url)
            self.execute_query(query, data)
            print "Added source for EpisodeId: %s, Source: %s, Link: %s" % (
                                                    episode_id, source, url)
        except Exception, ex:
            print "Couldn't save the source: %s" % ex
            raise ex # propagate the exception

    def mark_sources_as_downloaded(self, episode_id):
        """
        Update the DB marking the movie sources as 'downloaded'.
        """
        try:
            data = (1, episode_id)
            query = 'UPDATE series_episodes SET sources=? WHERE id=?'
            self.execute_query(query, data)
        except Exception, ex:
            print "Couldn't mark sources as downloaded: %s" % ex
            raise ex


    def download_subtitles(self):
        """
        Download the subtitles for all episodes that need it.
        """
        print "***** Start downloading subtitles... *****"
        try:
            query = 'SELECT id, name FROM series_episodes WHERE subs=0'
            episodes = self.run_query(query, as_list=True)
            for episode in episodes:
                (episode_id, episode_name) = episode
                for lang in freevana.SUBTITLES_LANGUAGES:
                    print "Downloading subs for #%s - %s in %s" % (episode_id,
                                                        episode_name, lang)
                    self.download_subtitle(episode_id, lang)
                self.mark_subs_as_downloaded(episode_id)
        except Exception, ex:
            print "Could not download subtitles: %s" % ex
            raise ex # propagate the exception

    def download_subtitle(self, episode_id, lang):
        """
        Download a Subtitle in a specific language
        """
        try:
            url = SUBTITLES_URL_PATTERN % (episode_id, lang)
            self.browser.retrieve(url, filename="%s/%s_%s.srt" % (
                            "%s/%s" % (SUBTITLES_LOCATION, lang),
                            episode_id, lang))
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

    def mark_subs_as_downloaded(self, episode_id):
        """
        Update the DB marking the episode's subs as downloaded.
        """
        try:
            data = (1, episode_id)
            query = 'UPDATE series_episodes SET subs=? WHERE id=?'
            self.execute_query(query, data)
        except Exception, ex:
            print "Couldn't mark subs as downloaded: %s" % ex
            raise ex # propagate the exception

"""
Note: episode names are only saved in their "short" version
      this means that some names might be truncated.
      This is because downloading the full names requires
      accessing an extra HTML page for each episode which
      would greatly increase the http usage and don't really
      provide any extra functionality.
      Because of this, episode names are saved in the 'short_name'
      column leaving the 'name' column empty for now.
      We might add support for downloading full names later.
"""