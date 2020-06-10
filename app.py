import re
from os import environ
import cfscrape
import flask
from bs4 import BeautifulSoup
from flask import request, jsonify
from flask_caching import Cache

from resources import utility
from resources.stopwatch import Timer

config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "simple", # Flask-Caching related configs
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
    download_link = get_download_link_ep(url)
    app.logger.info(timer.stop())

    return jsonify("download_link", download_link), 200


@cache.memoize(50)
def get_download_link_ep(url):
    delay = environ.get('CF_DELAY')
    scraper = cfscrape.create_scraper(delay=delay)
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
    return re.match(r'var fone="(.*?)";', unpacked)[1]


if __name__ == '__main__':
    try:
        app.logger.info(utility.utility_health())
    except():
        app.logger.error("Could not find utility package")
        quit(0)
    app.run(environ.get('PORT'))
