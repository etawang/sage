import copy
import mistune
import os
import pystache
import re
import shutil
import sys
import yaml
from pathlib import Path

ROOT_DIR = 'site-src'
GEN_DIR = 'sage'
BUILD_DIR = 'tmp-site-build'
FINAL_DIR = 'site-build'

# Constants used for rendering
ASSETS_DIR = os.path.join(GEN_DIR, 'assets')
TEMPLATES_DIR = os.path.join(GEN_DIR, 'templates')

GLOBAL_VARS_FILE = os.path.join(ROOT_DIR, 'global.yml')
BASIC_VARS = { 'url-home': '/', 'url-about': '/about/' }

MISTUNE = mistune.Markdown()

debug = False

def error_and_exit(msg):
    print(msg)
    exit(1)

def build_and_check_path(*arg):
    path = os.path.join(*arg)
    if not Path(path).exists():
        error_and_exit("Could not find file or directory at \"%s\"." % path)
    return path

def templates_home_path(*arg):
    return os.path.join(GEN_DIR, 'templates', 'homepage', *arg)

def templates_common_path(*arg):
    return os.path.join(GEN_DIR, 'templates', 'common', *arg)

def templates_posts_path(*arg):
    return os.path.join(GEN_DIR, 'templates', 'posts', *arg)

def templates_about_path(*arg):
    return os.path.join(GEN_DIR, 'templates', 'about', *arg)

def site_build_root_path(*arg):
    return os.path.join(BUILD_DIR, *arg)

def site_build_posts_path(*arg):
    return os.path.join(BUILD_DIR, 'posts', *arg)

def site_build_about_path(*arg):
    return os.path.join(BUILD_DIR, 'about', *arg)

def site_src_posts_path(*arg):
    return build_and_check_path(ROOT_DIR, 'posts', *arg)

def site_src_about_path(*arg):
    return build_and_check_path(ROOT_DIR, 'about', *arg)

def update_with_file_vars(vars_dict, fname):
    new_vars = {}
    with open(fname) as f:
        new_vars = yaml.safe_load(f)

    vars_dict.update(new_vars)

def update_with_vars_from_dir(vars_dict, dir_with_vars_file):
    src_files = os.listdir(dir_with_vars_file)

    # There should be at most one .yml file with post variables
    vars_file = first_match(re.compile('.*yml'), src_files)
    if vars_file != None:
        update_with_file_vars(vars_dict, os.path.join(dir_with_vars_file, vars_file))
    return vars_dict

def parse_global_vars(basic_vars):
    update_with_file_vars(basic_vars, GLOBAL_VARS_FILE)
    return basic_vars

def first_match(regex, li):
    matches = list(filter(lambda s: re.search(regex, s) != None, li))
    if len(matches) == 0:
        return None
    return matches[0]

# Move the assets into the top level of the build dir.
# Also create the build dir.
def move_assets():
    try:
        if os.path.exists(ASSETS_DIR):
            shutil.copytree(ASSETS_DIR, os.path.join(BUILD_DIR, 'assets'))
        else:
            os.mkdir(BUILD_DIR)
    except FileExistsError:
        error_and_exit("Temporary build directory %s already exists. Please remove and try again." % BUILD_DIR)

def move_site_build():
    try:
        shutil.copytree(BUILD_DIR, FINAL_DIR)
    except FileExistsError:
        error_and_exit("Build directory %s already exists. Please remove and try again." % FINAL_DIR)


def read_file(path):
    with open(path, 'r') as f:
        return f.read()
def required_fields_in_post_vars(post_vars):
    return set(['date', 'title']) <= set(post_vars.keys())

def get_all_post_vars():
    all_post_vars = {}
    for post_dir in os.listdir(site_src_posts_path()):
        post_vars = {}
        update_with_vars_from_dir(post_vars, site_src_posts_path(post_dir))
        post_vars['content'] = render_markdown_from_file(site_src_posts_path(post_dir))
        if debug:
            print("Resolved post variables...")
            print(list(post_vars.keys()))
        if not required_fields_in_post_vars(post_vars):
            error_and_exit("Post %s must have a date specified in the metadata file." % post_dir)
        all_post_vars[post_dir] = post_vars
    return all_post_vars

def render_markdown_from_file(content_dir):
    src_files = os.listdir(content_dir)

    # There should be exactly one .md file with post content
    content_file = first_match(re.compile('.*md'), src_files)

    if content_file == None:
        error_and_exit("Content not found for post \"%s\". Please create the file and try again." % content_dir)
    return MISTUNE(read_file(os.path.join(content_dir, content_file)))

def render_common(templ_vars):
    common_vars = {}
    for fname in os.listdir(templates_common_path()):
        templ = read_file(templates_common_path(fname))
        # Use the first word parsed out of the filename for referencing the rendered
        # template in the future.
        var_name = fname.split('.')[0]
        common_vars[var_name] = pystache.render(templ, templ_vars)
    templ_vars['common'] = common_vars
    return templ_vars

# post_templ: content of post template
# templ_vars: template variables from common or global
# post_dir: the directory name of the current post being rendered
def render_post(post_templ, templ_vars, post_dir, post_vars):
    new_vars = copy.deepcopy(templ_vars)

    os.makedirs(site_build_posts_path(post_dir))
    new_vars['post'] = post_vars
    with open(site_build_posts_path(post_dir, 'index.html'), 'w') as f:
        f.write(pystache.render(post_templ, new_vars))

def render_posts(templ_vars):
    post_templ = read_file(templates_posts_path('index.html.mustache'))

    for dname, post_vars in get_all_post_vars().items():
        if debug:
            print("Rendering post...")
            print(dname)
        render_post(post_templ, templ_vars, dname, post_vars)

def render_about(templ_vars):
    new_vars = copy.deepcopy(templ_vars)
    templ = read_file(templates_about_path('index.html.mustache'))

    about_vars = {}
    update_with_vars_from_dir(about_vars, site_src_about_path())
    about_vars['content'] = render_markdown_from_file(site_src_about_path())

    os.makedirs(site_build_about_path())
    new_vars['about'] = about_vars
    if debug:
        print("Resolved about variables...")
        print(list(about_vars.keys()))
    with open(site_build_about_path('index.html'), 'w') as f:
        f.write(pystache.render(templ, new_vars))

def update_with_post_list_vars(posts, templ_vars):
    # TODO: parse date and sort in reverse order
    posts_date = sorted(posts, key = lambda post: post['date'])
    templ_vars['post-snippets-date'] = posts_date

def render_home(templ_vars):
    new_vars = copy.deepcopy(templ_vars)
    templ = read_file(templates_home_path('index.html.mustache'))

    posts = []
    for dname, post_vars in get_all_post_vars().items():
        post_vars['url'] = "/posts/%s/" % dname
        posts.append(post_vars)
    update_with_post_list_vars(posts, new_vars)
    with open(site_build_root_path('index.html'), 'w') as f:
        f.write(pystache.render(templ, new_vars))

def render_site():
    move_assets()

    templ_vars = parse_global_vars(BASIC_VARS)
    if debug:
        print("Parsed global vars...")
        print(templ_vars)

    # Render common templates
    templ_vars = render_common(templ_vars)
    if debug:
        print("Rendered common templates...")
        print(templ_vars.keys())

    # Render posts
    render_posts(templ_vars)

    # Render about page
    render_about(templ_vars)

    # Render the homepage
    render_home(templ_vars)

    # Move build dir into final dir
    move_site_build()
    shutil.rmtree(BUILD_DIR)

# This script must be run from the directory above generator/
def main():
    global debug
    if len(sys.argv) > 1:
        if '-d' in sys.argv or '--debug' in sys.argv:
            debug = True
        if '-c' in sys.argv or '--clean' in sys.argv:
            if Path(BUILD_DIR).exists():
                shutil.rmtree(BUILD_DIR)
            if Path(FINAL_DIR).exists():
                shutil.rmtree(FINAL_DIR)
    render_site()

if __name__ == '__main__':
    main()
