import lib.config3 as config
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
import requests
import plexapi.exceptions
import sys, xmltodict, requests, urllib3, logging, time
from plexapi.server import PlexServer
from tqdm import tqdm
import lib.sodarr as sodarr

conf = config.conf

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

def check():
	sdr = sodarr.API(conf['sonarr']['host'] + '/api', conf['sonarr']['api'])
	from_profile = sdr.get_profile_id('Hold')
	to_profile = sdr.get_profile_id('Best')

	plex = PlexServer(conf['plex']['host'], conf['plex']['api'])
	users = [ user.title for user in plex.myPlexAccount().users() ]
	users.insert(0, plex.myPlexAccount().username)

	series = sdr.get_series()
	for show in series:
		tag_id = 0
		if show['profileId'] == from_profile:
			show['tags'] = [2]
			show['qualityProfileId'] = to_profile
			show['profileId'] = to_profile
			show['monitored'] = True
			for x in show['seasons']:
				x['monitored'] = False
			sdr.upd_series(show)
		try:
			tag_id = show['tags'][0]
		except:
			pass

		if tag_id == 2:
			logger.info("Starting %s" % show['title'])
			x = check_episodes(sdr, show, users)
			if x > 0:
				sdr.command({'name':'SeriesSearch', 'seriesId':show['id']})
				logger.info("%s Episodes for %s changed to monitor, sending search command" % (x, show['title']))

def check_episodes(sdr, series, users):
	all_episodes = sdr.get_episodes_by_series_id(series['id'])
	last_watched = 0
	num_changed = 0
	watch = False
	highest_season = 1
	for x in series['seasons']:
		if x['monitored']:
			if highest_season <= x['seasonNumber']:
				highest_season = x['seasonNumber']

		if highest_season == x['seasonNumber']: season_count = x['statistics']['totalEpisodeCount']

	for episode in tqdm(all_episodes):
		if episode['seasonNumber'] == highest_season:
			if episode['hasFile']:
				for user in tqdm(users):
					try:
						plex_episode = get_episode(series['title'], episode['seasonNumber'], episode['episodeNumber'], user=user)
						if not plex_episode: break
						watch_indiv = True if get_selected_viewOffset(plex_episode) == -1 else False
					except AttributeError:
						watch_indiv = False
					except Exception as e:
						logger.error('Error on line {}, {}, {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))

					if watch_indiv:
						watch = True
						if last_watched<episode['episodeNumber']: last_watched = episode['episodeNumber']
						break

	max_season = highest_season
	if last_watched < 3:
		max_episode = 5
	else:
		max_episode = season_count

	if (last_watched/season_count) >= .8:
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

	logger.info("%s - Monitor to S%sE%s - Last Watched S%sE%s" % (series['title'], max_season, max_episode, highest_season, last_watched))

	return num_changed

def get_episode(series_title, season_number, episode_number, user):
	try:
		plex_temp = PlexServer(conf['plex']['host'], conf['plex']['api'])
		if user != plex_temp.myPlexAccount().username:
			plex_users = get_user_tokens(plex_temp.machineIdentifier)
			token = plex_users[user]
			plex_temp = PlexServer(conf['plex']['host'], token)
		with  DisableLogger():
			episode = plex_temp.library.section('TV Shows').searchShows(title=series_title)[0].episode(season=season_number, episode=episode_number)
		
		return episode
	except plexapi.exceptions.NotFound:
#		logger.warn("Episode Not Found in Plex.")
		return False
	except Exception as e:
		logger.error('Error on line {}, {}, {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		logger.error('Error! Code: {c}, Message, {m}'.format(c = type(e).__name__, m = str(e)))
		return None

def create_media_lists(movie):
	try:
		patched_items = []
		for zomg in movie.media:
			zomg._initpath = movie.key
			patched_items.append(zomg)

		zipped = zip(patched_items, movie.iterParts())
		parts = sorted(zipped, key=lambda i: i[1].size, reverse=True)
		return parts
	except Exception as e:
		logger.error('Error on line {}, {}, {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		return None

def get_selected_viewOffset(video):
	if video.viewOffset == 0:
		if video.viewCount > 0:
			selected_viewOffset = -1
		else:
			selected_viewOffset = 0
	else:
		selected_viewOffset = video.viewOffset
	return selected_viewOffset

def get_user_tokens(server_id):
	try:
		headers = {'X-Plex-Token':  conf['plex']['api'], 'Accept': 'application/json'}
		api_users = xmltodict.parse(requests.get('https://plex.tv/api/users', headers=headers, params={}, verify=False).content)
		api_shared_servers = xmltodict.parse(requests.get('https://plex.tv/api/servers/{server_id}/shared_servers'.format(server_id=server_id), headers=headers, params={}, verify=False).content)
		user_ids = {user['@id']: user.get('@username', user.get('@title')) for user in api_users['MediaContainer']['User']}
		users = {user_ids[user['@userID']]: user['@accessToken'] for user in api_shared_servers['MediaContainer']['SharedServer']}
		return users
	except Exception as e:
		logger.error('Error on line {}, {}. {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		return None

class DisableLogger():
	def __enter__(self):
		logging.disable(logging.CRITICAL)
	def __exit__(self, a, b, c):
		logging.disable(logging.NOTSET)
