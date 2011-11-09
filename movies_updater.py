#!/usr/bin/env python
__author__ = "Tirino"

from freevana import TemporaryErrorException
from freevana.movies import MoviesUpdater

def main():
    """
    Entry point
    """
    updater = MoviesUpdater()
    loop = True
    while (loop):
        try:
            updater.update_movie_list()
            updater.process_sources()
            updater.download_subtitles()
            loop = False
        except KeyboardInterrupt, ex:
            print "Aborting... "
            return
        except TemporaryErrorException, ex:
            print "Movies site is temporary down. Will retry..."
        except Exception, ex:
            print "An unexpected error ocurred. Will retry... "
            print "(Error was: %s)" % str(ex)

if (__name__ == '__main__'):
    main()
