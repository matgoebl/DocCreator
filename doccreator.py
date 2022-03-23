l#!/usr/bin/env python3

import argparse
import dotenv
import os
import sys
import logging
import readline
import atexit
import subprocess
import os
import json
import jsonpath_ng
import re
import time

BRANCH_PREFIX = "doccreator"


class DocCreator:
    def __init__(self, base_path, template_file):
        self.__base_path = base_path
        self.name("unknown")
        template_filename = os.path.join(self.__base_path, template_file)
        with open(template_filename) as f:
            self.__doc = json.load(f)

    def __str__(self):
        return json.dumps(self.__doc, indent=4) + '\n'

    def set(self, field, value):
        jsonpath_expr = jsonpath_ng.parse(field)
        self.__doc = jsonpath_expr.update(self.__doc, value)

    def get(self, field):
        jsonpath_expr = jsonpath_ng.parse(field)
        return ",".join([str(match.value) for match in jsonpath_expr.find(self.__doc) if match.value != None])

    def name(self, newname, commondir=None):
        newname = re.sub(r'[^a-zA-Z]', '', newname)
        newname = newname[:16]
        self.__name = newname
        self.__commondir = commondir
        if commondir:
            self.__path = os.path.join(self.__base_path, commondir)
        else:
            self.__path = os.path.join(self.__base_path, self.__name)
        self.__filename = os.path.join(self.__path, self.__name + ".json")

    def write(self):
        if self.__commondir:
            os.makedirs(self.__path, exist_ok=True)
        else:
            if os.path.exists(self.__path):
                raise Exception(f"Path '{self.__path}' already exists.")
            os.mkdir(self.__path)
        if os.path.exists(self.__filename):
            raise Exception(f"File '{self.__filename}' already exists.")
        with open(self.__filename, 'w') as f:
            f.write(str(self))

    def pushbranch(self, dryrun=False):
        out = []
        branch = BRANCH_PREFIX + "-" + self.__name + "-" + str(int(time.time()))
        out.append(cmd(f"git checkout master"))
        out.append(cmd(f"git checkout -b {branch}"))
        out.append(cmd(f"git add {self.__filename}"))
        out.append(cmd(f"git commit -m 'new from template' {self.__filename}"))
        if not dryrun:
            out.append(cmd(f"git push --set-upstream origin {branch}"))
        return '\n'.join(out)


def cmd(cmdline):
    try:
        return f"+ {cmdline}\n" + subprocess.check_output(cmdline, shell=True, stderr=subprocess.STDOUT).decode('utf-8')
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error while executing '{e.args[1]}':\n{e.stdout.decode('utf-8')}")



readline_history_file = os.environ.get('DOCCREATOR_HISTORY','.doccreator.history')

def save_readline_history():
    readline.write_history_file(readline_history_file)

def input_prefilled(prompt, prefill=""):
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt)
    finally:
        readline.set_startup_hook()



def main():
    dotenv.load_dotenv(os.environ.get('DOTENV','.env'))
    parser = argparse.ArgumentParser(
        description='Tool to create JSON documents by filling templates and commiting them to git repositories.',
        epilog='For details see https://github.com/matgoebl/DocCreator .')
    parser.add_argument('-p', '--gitrepopath',default=".",               help='Set git repository path.' )
    parser.add_argument('-d', '--commondir',  default=None,              help='Write document to a common directory, otherwise create new directory base on given name.')
    parser.add_argument('-t', '--template',   default='template.json',   help='Set template file name relative to git repository path.')
    parser.add_argument('-f', '--fields',     default='Name,Details.Location,Details.Type',   help='List of fields to replace, comma separated.')
    parser.add_argument('-r', '--readfile',   default=None,              help='Read input from file.')
    parser.add_argument('-i', '--interactive',action='store_true',       help='Run creation interactive.' )
    parser.add_argument('-n', '--dryrun',     action='store_true',       help='Do not push branch.' )
    parser.add_argument('--test',             action='store_true',       help='Run a test.' )
    parser.add_argument('-v', '--verbose',    action='count', default=int(os.environ.get('VERBOSE','0')), help="Be more verbose, can be repeated (up to 3 times)." )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING-10*args.verbose,handlers=[logging.StreamHandler()],format="[%(levelname)s] %(message)s")


    try:
        doc = DocCreator(args.gitrepopath, args.template)
        if args.verbose >= 2:
            print(f"Source document:\n{doc}")

        if args.test:
            doc.set('Name','Test')
            doc.name("1. Test - This is just a SMALL test...", args.commondir)

        elif args.readfile:
            with open(args.readfile) as f:
                doc.name(f.read(), args.commondir)
                for field in args.fields.split(','):
                    doc.set(field,f.read())

        elif args.interactive:
            if os.path.isfile(readline_history_file):
                readline.read_history_file(readline_history_file)

            atexit.register(save_readline_history)

            for field in args.fields.split(','):
                val = input_prefilled(f"{field}: ", doc.get(field))
                doc.set(field,val)
            doc.name(doc.get('Name'))

        else:
            sys.exit(0)

        if args.verbose:
            print(f"Result document:\n{doc}")
        doc.write()
        out = doc.pushbranch()
        print(out)

    except Exception as e:
        print(f"Error: {e}")

    sys.exit(0)


if __name__ == '__main__':
    main()
