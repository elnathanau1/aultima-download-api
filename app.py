import flask
from os import environ
from flask import request, jsonify
from bs4 import BeautifulSoup
import cfscrape
import re
import utility

app = flask.Flask(__name__)
# app.config["DEBUG"] = True


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

if __name__ == '__main__':
    app.run(environ.get('PORT'))

