#!/usr/bin/env python3
import dotenv
import argparse
import sys
import re
import json
import os
import logging
import yaml
import glob
import copy
import datetime
import jsonpath_ng
import urllib.parse
import importlib
from string import Template
from flask import Flask, request, render_template, make_response, g
from jinja2 import Environment, select_autoescape
from werkzeug.middleware.proxy_fix import ProxyFix

import doccreator

has_dotenv = True if os.environ.get('DOTENV') != None else False
dotenv.load_dotenv(os.environ.get('DOTENV','.env'), verbose = has_dotenv, override = has_dotenv)

verbose = int(os.environ.get('VERBOSE','1'))
port = int(os.environ.get('PORT','8008'))


gitrepopath  = os.environ.get('GITREPOPATH', '.')
gitrepourl   = os.environ.get('GITREPOURL', None)
commondir    = os.environ.get('COMMONDIR', None)
branchprefix = os.environ.get('BRANCHPREFIX', 'doccreator')
nameprefix   = os.environ.get('NAMEPREFIX', '')
template     = os.environ.get('TEMPLATE', 'template.json')
fields       = os.environ.get('FIELDS', '').split(';')
dryrun = False

logging.basicConfig(level=logging.WARNING-10*verbose,handlers=[logging.StreamHandler()],format="[%(levelname)s] %(message)s")

Flask.jinja_options = {
    'autoescape': select_autoescape(
        disabled_extensions=('txt'),
        default_for_string=True,
        default=True),
    'line_statement_prefix': '%'
}
app = Flask(__name__)


@app.route("/",methods = ['GET', 'POST'])
def index():
    results = None
    errormsg = None

    if request.method == 'POST':
        args = request.form
    else:
        args = request.args

    try:
        name = args.get('Name')
        if name and len(name) > 0:

            doc = doccreator.DocCreator(os.path.join(gitrepopath,"worker-"+str(os.getpid())), gitrepourl, template, nameprefix)
            if verbose:
                print(f"Output:\n{doc.out}")
            if verbose >= 2:
                print(f"Source document:\n{doc}")

            doc.name(name, commondir)
            for field in fields:
                field = field.strip()
                if field.find('=') >= 0:
                    field,default = field.split('=',2)
                doc.set(field,args.get(field))

            if verbose >= 2:
                print(f"Result document for {doc.get('Name')}:\n{doc}")
            doc.write()
            results = doc.pushbranch(branchprefix, dryrun)
            if verbose:
                print(results)

    except Exception as e:
        errormsg = repr(e)
        logging.exception("Error while parsing request:")

    logging.debug(f"Results: {yaml.dump(results)}")

    return render_template('index.html.jinja', args=args, results=results, errormsg=errormsg, fields=fields)



@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        response.headers["Cache-Control"] = "no-store, max-age=0"

    return response

app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
