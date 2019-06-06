import lib.config3 as config
config.main()
import logging
import plexapi.exceptions
import sys, urllib3, logging, time
from plexapi.server import PlexServer
import lib.sodarr as sodarr

conf = config.conf

sdr = sodarr.API(conf['sonarr']['host'] + '/api', conf['sonarr']['api'])

logger = logging.getLogger(__name__)

def main():
	plex = PlexServer(conf['plex']['host'], conf['plex']['api'])

	for x in plex.sessions():
		try:
			logger.info("User: %s is watching %s" % (x.usernames[0], create_plex_title(x)))
			(series, max_season, season_count) = sonarr_info_by_tvbdb(x.guid.split('/')[2])
			if 2 in series['tags']:
				logger.info("Checking  %s" % series['title'])
				remaining_episodes = series['totalEpisodeCount'] - (series['seasons'][0]['statistics']['totalEpisodeCount'] if series['seasons'][0]['seasonNumber'] == 0 else 0) - series['episodeCount']
				if remaining_episodes > 0:
					x = update_show(series, max_season, season_count, x.index)
					x = 0
					if x > 0:
						sdr.command({'name':'SeriesSearch', 'seriesId':show['id']})
						logger.info("%s Episodes for %s changed to monitor, sending search command" % (x, show['title']))
				else:
					logger.info("Monitoring All Episodes for %s" % show['title'])

			else:
				logger.info("Show: %s is Not Ombi" % series['title'])
		except:
			logger.info("Show Not Found in Sonarr")
			pass

def create_plex_title(video):
	if video.type == "movie":
		try:
			title = "%s (%s)" % (video.title, video.originallyAvailableAt.strftime("%Y"))
		except:
			title = video.title
	else:
		title = "%s - %s - %s" % (video.grandparentTitle, video.parentTitle, video.title)
	return title



def sonarr_info_by_tvbdb(tvdb):
	series = sdr.get_series()
	for show in series:
		if tvdb == str(show['tvdbId']):
			(highest_season, season_count) =  get_highest_season(show)
			return (show, highest_season, season_count)

def update_show(series, last_season, season_count, last_episode):
	all_episodes = sdr.get_episodes_by_series_id(series['id'])
	max_season = last_season
	num_changed = 0

	if last_episode < 3:
		max_episode = 5
	else:
		max_episode = season_count

	if (last_episode/season_count) >= .75:
		max_season+=1
		max_episode=5

	for x in series['seasons']:
		monitor = False
		if x['seasonNumber'] <= max_season and x['seasonNumber'] > 0: monitor = True
		x['monitored'] = monitor
		sdr.upd_series(series)

	for episode in all_episodes:
		try:
			monitor = False
			if episode['seasonNumber'] > 0 and episode['seasonNumber'] <= max_season:
				if episode['seasonNumber'] == max_season and episode['episodeNumber'] <= max_episode:
					monitor = True
				elif episode['seasonNumber'] != max_season:
					monitor = True
			if episode['monitored'] != monitor:
				if monitor: num_changed+=1
			episode['monitored'] = monitor
			sdr.upd_episode(episode)
			time.sleep(1)
		except Exception as e:
			logger.error('Error! Line: {l}, Code: {c}, Message, {m}'.format(l = sys.exc_info()[-1].tb_lineno, c = type(e).__name__, m = str(e)))
			pass

	logger.info("%s - Monitor to S%sE%s - Last Watched S%sE%s" % (series['title'], max_season, max_episode, last_season, last_episode))
	return num_changed

def get_highest_season(series):
	highest_season = 1
	for x in series['seasons']:
		if x['monitored']:
			if highest_season <= x['seasonNumber']:
				highest_season = x['seasonNumber']

		if highest_season == x['seasonNumber']:
			season_count = x['statistics']['totalEpisodeCount']

	return (highest_season, season_count)
