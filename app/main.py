import flask
from os import environ
# from flask import request, jsonify
# from bs4 import BeautifulSoup

app = flask.Flask(__name__)
app.run(environ.get('PORT'))
# app.config["DEBUG"] = True


@app.route('/', methods=['GET'])
def home():
    return "<h1>aultima-api-flask</h1><p>This is an api for retrieving download links from aultima.</p>"

@app.route('/health', methods=['GET'])
def health():
    return "OK"

app.run()
