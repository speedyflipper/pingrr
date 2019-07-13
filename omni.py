import lib.config3 as config
import logging
import plexapi.exceptions
import sys, urllib3, logging, time, xmltodict, requests
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_DOWN
from plexapi.server import PlexServer
import lib.sodarr as sodarr

conf = config.conf
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sdr = sodarr.API(conf['sonarr']['host'] + '/api', conf['sonarr']['api'])

logger = logging.getLogger(__name__)

def modify_new():
	from_profile = sdr.get_profile_id('Hold')
	to_profile = sdr.get_profile_id('Best')

	series = sdr.get_series()
	for show in series:
		try:
			if show['profileId'] == from_profile:
				logger.info("New Show (%s) Found for Omni, Making Initial Changes" % show['title'])
				show['tags'] = [2]
				show['qualityProfileId'] = to_profile
				show['profileId'] = to_profile
				show['monitored'] = True
				for x in show['seasons']: x['monitored'] = False
				sdr.upd_series(show)

				(highest_season, season_count) =  get_highest_season(show)
				update_show(show, highest_season, season_count, 0)

		except Exception as e:
			if config.DEBUG: logger.error('Error on line {}, {}. {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))

def session_search():
	plex = PlexServer(conf['plex']['host'], conf['plex']['api'])

	for x in plex.sessions():
		try:
			logger.info("User: %s is watching %s" % (x.usernames[0], create_plex_title(x)))
			if x.type == "episode":
				(series, max_season, season_count) = sonarr_info_by_tvbdb(x.guid.split('/')[2])
				if 2 in series['tags']:
					remaining_episodes = series['totalEpisodeCount'] - (series['seasons'][0]['statistics']['totalEpisodeCount'] if series['seasons'][0]['seasonNumber'] == 0 else 0) - series['episodeCount']
					if remaining_episodes > 0:
						update_show(series, int(x.parentIndex), season_count, int(x.index))
					else:
						logger.info("Monitoring All Episodes for %s" % series['title'])
		except:
			logger.error("Show Not Found in Sonarr")

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

	if config.DEBUG: logger.info("Calculating New Stats for Show")
	if (last_episode < 3) and (season_count > 8):
		max_episode = 5
	else:
		max_episode = season_count

	if ((last_episode/season_count) >= .75) or (last_episode > 3 and season_count < 8):
		max_season+=1
		max_episode=5

	if config.DEBUG: logger.info("Marking Seasons")
	for x in series['seasons']:
		monitor = False
		if x['seasonNumber'] <= max_season and x['seasonNumber'] > 0: monitor = True
		x['monitored'] = monitor
		sdr.upd_series(series)

	if config.DEBUG: logger.info("Marking Episodes")
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
	if num_changed > 0:
		sdr.command({'name':'SeriesSearch', 'seriesId': series['id']})
		logger.info("%s Episodes for %s changed to monitor, sending search command" % (num_changed, series['title']))

def get_highest_season(series):
	highest_season = 1
	if config.DEBUG: logger.info("Getting Highest Monitored Season")
	for x in series['seasons']:
		if x['monitored'] and x['statistics']['episodeCount'] > 0:
			if highest_season <= x['seasonNumber']:
				highest_season = x['seasonNumber']

		if highest_season == x['seasonNumber']:
			season_count = x['statistics']['totalEpisodeCount']
	
	return (highest_season, season_count)

def search_users(series, users, season_number, episode_number):
	watch = False
	for index, user in enumerate(users):
		if config.DEBUG: logger.info("Checking User: %s (%s/%s)" % (user, index + 1, len(users)))
		watch_indiv = False
		try:
			plex_episode = get_episode(series['title'], season_number, episode_number, user=user)
			if not plex_episode: break
			watch_indiv = True if get_selected_viewOffset(plex_episode) == -1 else False
		except AttributeError:
			watch_indiv = False
		except Exception as e:
			logger.error('Error on line {}, {}, {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
			watch_indiv = False

		if watch_indiv:
			watch = True
			break
	return watch

def find_last_watched(series, users):
	episode_count = 0
	last_watched = 0
	all_episodes = sdr.get_episodes_by_series_id(series['id'])
	(highest_season, season_count) = get_highest_season(series)
	if config.DEBUG: logger.info("Checking for Highest Watch Episode in Season %s" % highest_season)
	last_watched = search_season(series, users, highest_season, season_count)
	return last_watched, highest_season, season_count
	
def search_season(series, users, season, last):
	first = 0
	watch = False
	index = 0
	while first != last:
		index+=1
		
		if index == 2:
			if watch:
				midpoint = last
			else:
				midpoint = 1
		else:
			midpoint = Decimal((first + last)/2).to_integral_value(rounding=ROUND_HALF_UP)
			if first == midpoint or last == midpoint:
					midpoint = Decimal((first + last)/2).to_integral_value(rounding=ROUND_HALF_DOWN)
					if first == midpoint or last == midpoint: break

		if config.DEBUG: logger.info("Checking Episode: %s" % midpoint)
		watch = search_users(series, users, season, midpoint)
		if watch:
			first = midpoint
		else:
			last = midpoint
		
	return first
	
def full_check():
	from_profile = sdr.get_profile_id('Hold')
	to_profile = sdr.get_profile_id('Best')

	plex = PlexServer(conf['plex']['host'], conf['plex']['api'])
	users = [ user.title for user in plex.myPlexAccount().users() ]
	users.insert(0, plex.myPlexAccount().username)

	series = sdr.get_series()
	for show in series:
		try:
			try:
				tag_id = show['tags'][0]
			except:
				tag_id = 0
			if tag_id == 2:
				logger.info("Starting %s" % show['title'])
				remaining_episodes = show['totalEpisodeCount'] - (show['seasons'][0]['statistics']['totalEpisodeCount'] if show['seasons'][0]['seasonNumber'] == 0 else 0) - show['episodeCount']
				if remaining_episodes > 0:
					(last_watched, highest_season, season_count) = find_last_watched(show, users)
					update_show(show, highest_season, season_count, last_watched)
				else:
					logger.info("Monitoring All Episodes for %s" % show['title'])
		except Exception as e:
			logger.error('Error on line {}, {}. {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
			
def get_episode(series_title, season_number, episode_number, user):
	try:
		pause = 0
		while True:
			pause+=1
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
				return False
			except:
				time.sleep(pause)
				continue
	except plexapi.exceptions.NotFound:
		return False
	except Exception as e:
		logger.error('Error on line {}, {}, {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		logger.error('Error! Code: {c}, Message, {m}'.format(c = type(e).__name__, m = str(e)))
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
		api_shared_servers = xmltodict.parse(requests.get('https://plex.tv/api/servers/{server_id}/shared_servers'.format(server_id=server_id), headers=headers, params={}, verify=False).content)
		users = {'speedy' if not user['@username'] else user['@username']: user['@accessToken'] for user in api_shared_servers['MediaContainer']['SharedServer']}
		return users
	except Exception as e:
		logger.error('Error on line {}, {}. {}'.format(sys.exc_info()[-1].tb_lineno, type(e).__name__, e))
		return None

class DisableLogger():
	def __enter__(self):
		logging.disable(logging.CRITICAL)
	def __exit__(self, a, b, c):
		logging.disable(logging.NOTSET)