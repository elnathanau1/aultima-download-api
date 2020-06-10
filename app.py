import concurrent.futures
import re
from os import environ
import cfscrape
import flask
from bs4 import BeautifulSoup
from flask import request, jsonify
from flask_caching import Cache
import json
from retrying import retry

from resources import utility
from resources.stopwatch import Timer

DEFAULT_MAX_WORKERS = 10

config = {
    "DEBUG": True,  # some Flask specific configs
    "CACHE_TYPE": "simple",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
}
app = flask.Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)


@app.route('/', methods=['GET'])
def home():
    return "<h1>aultima-api-flask</h1><p>This is an api for retrieving download links from aultima.</p>"


@app.route('/health', methods=['GET'])
def health():
    return "OK"


@app.route('/get/episode', methods=['POST'])
def create_task():
    # validate request body
    if not request.json or not 'url' in request.json:
        flask.abort(400)

    # get site contents
    url = request.json['url']
    scraper = cfscrape.create_scraper()
    content = scraper.get(url).content

    # beautifulsoup scrape
    soup = BeautifulSoup(content, 'html.parser')
    source = soup.find("iframe")["src"]
    js = scraper.get("https://www1.animeultima.to" + source).content

    js_soup = BeautifulSoup(js, 'html.parser')
    script_tag = js_soup.findAll("script")
    script = script_tag[-1].string
    script = script.strip()

    unpacked = eval('utility.unpack' + script[script.find('}(') + 1:-1])
    download_link = re.match(r'''var fone="(.*?)";''', unpacked)[1]

    return jsonify("download_link", download_link), 200


@app.route('/get/episode', methods=['POST'])
def get_episode():
    # validate request body
    if not request.json or not 'url' in request.json:
        flask.abort(400)

    # get site contents
    url = request.json['url']
    app.logger.info("Getting download link from %s", url)
    timer = Timer()
    timer.start()
    download_link = scrape_download_link_ep(url)
    app.logger.info(timer.stop())

    return jsonify("download_link", download_link), 200


@app.route('/get/season/download_links', methods=['POST'])
def get_season_download_links():
    if "MAX_WORKERS" in environ:
        max_workers = environ.get("MAX_WORKERS")
    else:
        max_workers = DEFAULT_MAX_WORKERS
    # validate request body
    # refactor?
    if not request.json or not 'url' in request.json or not 'show_name' in request.json or not 'season' in request.json:
        flask.abort(400)

    timer = Timer()
    timer.start()
    # create thread pool
    episode_list = scrape_episode_list(request.json['url'], request.json['show_name'], request.json['season'])
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS) as executor:
        for name, link in episode_list:
            future = executor.submit(scrape_download_link_ep, link)
            futures.append((name, future))

    # get results
    download_list = []
    for name, future in futures:
        try:
            download_link = future.result()
            download_list.append((name, download_link))
        except:
            app.logger.error("Failed to get download link for %s" % name)
    app.logger.info(timer.stop())

    json_list = []
    for name, link in download_list:
        json_list.append({'name': name, 'url': link})
        app.logger.info("Finished %s" % name)

    return json.dumps(json_list)

@app.route('/get/season/episodes', methods=['POST'])
def get_season_episodes():
    # validate request body
    # refactor?
    if not request.json or not 'url' in request.json or not 'show_name' in request.json or not 'season' in request.json:
        flask.abort(400)

    timer = Timer()
    timer.start()
    # create thread pool
    episode_list = scrape_episode_list(request.json['url'], request.json['show_name'], request.json['season'])
    app.logger.info(timer.stop())

    json_list = []
    for name, link in episode_list:
        json_list.append({'name': name, 'url': link})
        app.logger.info("Finished %s" % name)

    return json.dumps(json_list)


# @cache.memoize(50)
@retry(stop_max_attempt_number=5, wait_random_min=1000, wait_random_max=4000)
def scrape_download_link_ep(url):
    delay = environ.get('CF_DELAY')
    scraper = cfscrape.create_scraper(delay=delay)
    content = scraper.get(url).content
    # beautifulsoup scrape
    soup = BeautifulSoup(content, 'html.parser')
    iframe = soup.find("iframe")
    source = iframe["src"]
    js = scraper.get("https://www1.animeultima.to" + source).content

    js_soup = BeautifulSoup(js, 'html.parser')
    script_tag = js_soup.findAll("script")
    script = script_tag[-1].string
    script = script.strip()

    unpacked = eval('utility.unpack' + script[script.find('}(') + 1:-1])
    return re.match(r'var fone="(.*?)";', unpacked)[1]


def scrape_episode_list(url, show_name, season):
    scraper = cfscrape.create_scraper()
    content = scraper.get(url).content
    soup = BeautifulSoup(content, 'html.parser')
    show_id = soup.find("episode-list")["anime-id"]

    current_page = 1
    last_page = 1
    return_list = []
    while current_page <= last_page:
        parameters = {
            "animeId": show_id,
            "page": current_page
        }
        response = scraper.get("https://www1.animeultima.to/api/episodeList", params=parameters).content.decode()
        response = response.replace("\\", "")
        episode_list = json.loads(response)
        for episode in episode_list["episodes"]:
            episode_num = episode["episode_num"]
            episode_url = episode["urls"]["sub"]
            episode_name = "%s_S%s_E%s.mp4" % (show_name, season, episode_num)
            return_list.append((episode_name, episode_url))
        current_page += 1
        last_page = episode_list["last_page"]

    return return_list


if __name__ == '__main__':
    try:
        app.logger.info(utility.utility_health())
    except:
        app.logger.error("Could not find utility package")
        quit(0)
    app.run(environ.get('PORT'))
