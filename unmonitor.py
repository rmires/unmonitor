import yaml
import requests
import logging

class ApiRequester(object):
    def __init__(self, host, headers):
        self.host = host
        self.headers = headers
        self.logger = logging.getLogger(__name__)

    def get(self, endpoint, **kwargs):
        url = f"{self.host}{endpoint}"
        self.logger.debug(f"get url: {url}")
        self.logger.debug(f"get params: {kwargs}")
        response = requests.get(url, headers=self.headers, params=kwargs)
        response.raise_for_status()
        data = response.json()
        self.logger.debug(f"get data: {data}")
        return data

    def put(self, endpoint, payload):
        url = f"{self.host}{endpoint}"
        self.logger.debug(f"put url: {url}")
        self.logger.debug(f"put payload: {payload}")
        response = requests.put(url, headers=self.headers, json=payload)
        response.raise_for_status()

class Config(object):
    def __init__(self, config_path):
        with open(config_path, 'r') as file:
            config_data = yaml.safe_load(file)
        
        self.app = config_data['app']
        self.sonarr = config_data['sonarr']
        self.emby = config_data['emby']
        self.radarr = config_data['radarr']
        self.log = config_data['log']
        self.setup_logging(self.log)

    def setup_logging(self, config):
        logging.basicConfig(**config)

class Emby(ApiRequester):
    def __init__(self, config):
        super().__init__(config['host'], {"X-Emby-Token": config['api_key']})
        self.user_id = self.get_user_id(config['user_name'])

    def get_user_id(self, user_name):
        user_data = self.get(endpoint='/Users')
        user_id = [data["Id"] for data in user_data if data["Name"] == user_name][0]
        return user_id

    def get_watched_movies_tmdb_ids(self):
        data = self.get(endpoint=f"/Users/{self.user_id}/Items",
                        Recursive='true',
                        IsPlayed='true',
                        IncludeItemTypes='Movie',
                        Fields='ProviderIds')
        return [item['ProviderIds']['Tmdb'] for item in data['Items']]

    def get_watched_episodes_tvdb_ids(self):
        data = self.get(endpoint=f"/Users/{self.user_id}/Items",
                        Recursive='true',
                        IsPlayed='true',
                        IncludeItemTypes='Episode',
                        Fields='ProviderIds')
        return [item['ProviderIds']['Tvdb'] for item in data['Items']]

class Sonarr(ApiRequester):
    def __init__(self, config):
        super().__init__(config['host'], {"X-Api-Key": config['api_key']})

    def get_all_series(self):
        return self.get(endpoint='/api/v3/series')

    def get_all_episodes(self):
        all_episodes = []
        series = self.get_all_series()

        for serie in series:
            serie_id = serie["id"]
            episodes = self.get(endpoint=f"/api/v3/episode?seriesId={serie_id}")
            all_episodes.extend(episodes)

        return all_episodes

    def get_monitored_episodes_by_tvdb_ids(self, tvdb_ids):
        episodes_data = self.get_all_episodes()
        return [episode for episode in episodes_data 
                if str(episode['tvdbId']) in tvdb_ids and episode['monitored']]

    def unmonitor_episodes(self, episodes):
        if episodes:
            episodes_ids = [episode['id'] for episode in episodes]
            episodes_names = [episode['title'] for episode in episodes]
            payload = {"episodeIds":episodes_ids,"monitored": False}
            self.put(endpoint='/api/v3/episode/monitor', payload=payload)
            self.logger.info(f"unmonitored episodes: {episodes_names}")

class Radarr(ApiRequester):
    def __init__(self, config):
        super().__init__(config['host'], {"X-Api-Key": config['api_key']})

    def get_all_movies(self):
        return self.get(endpoint='/api/v3/movie')

    def get_monitored_movies_by_tmdb_ids(self, tmdb_ids):
        movie_data = self.get_all_movies()
        return [movie for movie in movie_data 
                if str(movie['tmdbId']) in tmdb_ids and movie['monitored']]

    def unmonitor_movies(self, movies):
        for movie in movies:
            movie['monitored'] = False
            movie_id = movie['tmdbId']
            self.put(endpoint=f"/api/v3/movie/{movie_id}", payload=movie)
            self.logger.info("unmonitored movie: " + movie['title'])

class App:
    def __init__(self, config_path):
        self.config = Config(config_path)
        self.emby = Emby(self.config.emby)
        self.sonarr = Sonarr(self.config.sonarr)
        self.radarr = Radarr(self.config.radarr)
        self.logger = logging.getLogger(__name__)

    def unmonitor_watched_episodes(self):
        watched_episodes_tvdb_ids = self.emby.get_watched_episodes_tvdb_ids()
        monitored_watched_episodes = self.sonarr.get_monitored_episodes_by_tvdb_ids(watched_episodes_tvdb_ids)
        self.sonarr.unmonitor_episodes(monitored_watched_episodes)

    def unmonitor_watched_movies(self):
        watched_movies_tmdb_ids = self.emby.get_watched_movies_tmdb_ids()
        monitored_watched_movies = self.radarr.get_monitored_movies_by_tmdb_ids(watched_movies_tmdb_ids)
        self.radarr.unmonitor_movies(monitored_watched_movies)

    def report_success(self):
        requests.get(self.config.app['health_check'])

    def run(self):
        try:
            if self.config.app['sonarr']:
                self.unmonitor_watched_episodes()

            if self.config.app['radarr']:
                self.unmonitor_watched_movies()

            if self.config.app['health_check']:
                self.report_success()
        except Exception as e:
            self.logger.exception(e)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Unmonitor watched episodes and movies on Emby.')
    parser.add_argument('config_path', help='Path to the configuration file.')

    args = parser.parse_args()

    app = App(args.config_path)
    app.run()
