#!/usr/bin/env python3

"""
collection of download operations
http://docs.python-guide.org/en/latest/scenarios/scrape/
http://stackabuse.com/download-files-with-python/
"""

__author__ = "Marco Volkert"
__copyright__ = "Copyright 2017, Marco Volkert"
__email__ = "marco.volkert24@gmx.de"
__status__ = "Development"

import os
import re
from collections import OrderedDict
from datetime import datetime
from http.cookies import SimpleCookie
from time import sleep
from typing import List, Union, Tuple
from enum import Enum
from filetools.helpers import read_file_as_bytes, isfile, modification_date
from lxml import html
import requests
from requests import Response

__all__ = ["downloadFiles", "downloadFilesFromGallery", "downloadFilesMulti", "firstAndLazyLoaded", "NameSource"]


class NameSource(Enum):
    URL = 0
    CONTENT = 1
    NAME = 2
    GALLERY = 3


class HtmlResolver:
    dest_main: str = None
    dirname_mainpage: str = None
    dirname_name: str = None
    dest_name: str = None
    dest_html: str = None
    last_date: datetime = datetime.now()

    def __init__(self, mainpage: str, name: str, sub_side: str = "", query="", pretty_print=False):
        self.http_path = _build_http_path(mainpage, sub_side, name, query)
        self._set_names(mainpage, name, pretty_print)

    def _set_names(self, mainpage: str, name: str, pretty_print=False):
        self.dest_main = os.getcwd()
        self.dirname_mainpage = _strip_url(mainpage)
        self.dirname_name = name.replace('/', '-')
        if pretty_print:
            self.dirname_name = pretty_name(self.dirname_name)
        self.dest_name = os.path.join(self.dest_main, self.dirname_mainpage, self.dirname_name)
        self.dest_html = os.path.join(self.dest_main, self.dirname_mainpage, 'html', self.dirname_name)

    def get_mainpage(self) -> bytes:
        raise Exception('not implemented')

    def set_referer(self, referer: str = None) -> None:
        return

    def get_html_files(self, urls: List[str], filename: str) -> List[bytes]:
        if len(urls) == 1:
            return [self.get_file(urls[0], self.dest_html, filename="%s.html" % filename)]
        else:
            return [self.get_file(url, self.dest_html, filename="%s_p%02d.html" % (filename, i + 1))
                    for i, url in enumerate(urls)]

    def get_file(self, url: str, dest: str, filename: str) -> bytes:
        raise Exception('not implemented')


def get_hrefs(page: bytes, xpath='//a', contains='') -> List[str]:
    if not page:
        return []
    tree = html.fromstring(page)
    elements = tree.xpath(xpath)
    hrefs = [x.get("href") if x.get("href") else x.get("src") for x in elements]
    hrefs = [href for href in hrefs if href and contains in href]
    return hrefs


def get_content(page: bytes, xpath: str) -> List[str]:
    if not page or not xpath:
        return []
    tree = html.fromstring(page)
    elements = tree.xpath(xpath)
    return [element.text_content() for element in elements]


def downloadFiles(mainpage: str, name: str, sub_side="", query="", g_xpath='//a', g_contains='', f_xpath='//a',
                  f_contains="", g_part=-1, f_part=-1, ext="", cookies: Union[dict, str] = None, paginator="",
                  name_source: NameSource = NameSource.URL, start_after="", pretty_print=False, description_xpath='',
                  description_gallery_xpath='', tags_gallery_xpath='', gallery_overview_info_xpath='',
                  statistic_only=False, analyse_local=False):
    if analyse_local:
        html_resolver = HtmlFileResolver(mainpage, name, sub_side, query=query, pretty_print=pretty_print)
    else:
        html_resolver = HtmlHttpResolver(mainpage, name, sub_side, query=query, pretty_print=pretty_print,
                                         cookies=cookies)

    # determine url of overview pages
    urls = [html_resolver.http_path]
    if paginator:
        mainpage_content = html_resolver.get_mainpage()
        pagination_hrefs = get_hrefs(mainpage_content, paginator)
        for paginationHref in pagination_hrefs:
            pagination_url = _createUrl(paginationHref, mainpage)
            urls.append(pagination_url)

    html_list = html_resolver.get_html_files(urls, html_resolver.dirname_name)

    # extract galleries
    galleries = []
    gallery_overview_info = []
    for html_page in html_list:
        galleries += get_hrefs(html_page, g_xpath, g_contains)
        if gallery_overview_info_xpath:
            gallery_overview_info += get_content(html_page, gallery_overview_info_xpath)
    if not galleries:
        return
    galleries = list(OrderedDict.fromkeys(galleries))
    galleries.reverse()
    gallery_overview_info.reverse()

    html_title = get_content(html_list[0], r"//title")[0]
    html_description = get_content(html_list[0], description_xpath)
    _log_name(html_resolver, galleries, html_title, html_description)
    found = False

    for i, gallery in enumerate(galleries):
        gallery_title = _strip_url(_extract_part(gallery, g_part))
        if start_after and not found:
            found = start_after == gallery_title
            continue
        dirname_gallery = '%03d_%s' % (i + 1, gallery_title)
        gallery_url = _createUrl(gallery, mainpage)
        html_list_gallery = html_resolver.get_html_files([gallery_url], dirname_gallery)
        file_urls = get_hrefs(html_list_gallery[0], f_xpath, f_contains)

        if len(file_urls) == 0:
            print("no file urls found for ", dirname_gallery)
            continue
        elif len(file_urls) == 1 or name_source == NameSource.GALLERY:
            dest_gallery = html_resolver.dest_name
        else:
            dest_gallery = os.path.join(html_resolver.dest_name, dirname_gallery)
            if os.path.exists(dest_gallery):
                continue
            if not statistic_only:
                os.makedirs(dest_gallery)
        print(dest_gallery)

        for j, file_url in enumerate(file_urls):
            file_url = _createUrl(file_url, mainpage)
            filename = _build_file_name(file_urls, j, f_part, ext, html_resolver.dirname_name, i, gallery_title,
                                        name_source)
            if j == 0:
                html_description_gallery = get_content(html_list_gallery[0], description_gallery_xpath)
                html_tags_gallery = get_content(html_list_gallery[0], tags_gallery_xpath)
                gallery_overview_info_entry = gallery_overview_info[i] if i < len(gallery_overview_info) else ''
                _log_gallery(html_resolver, dirname_gallery, filename, file_urls, gallery,
                             html_tags_gallery, html_description_gallery, gallery_overview_info_entry)
            if not statistic_only:
                download_file_direct(file_url, dest_gallery, filename, cookies=html_resolver.cookies,
                                     headers={'Referer': gallery_url}, name_source=name_source)


def downloadFilesMulti(mainpage: str, names: List[str], sub_side="", query="", g_xpath='//a', g_contains='',
                       f_xpath='//a', f_contains="", g_part=-1, f_part=-1, ext="", cookies: Union[dict, str] = None,
                       paginator="", name_source: NameSource = NameSource.URL, pretty_print=False, description_xpath='',
                       description_gallery_xpath='', tags_gallery_xpath='', gallery_overview_info_xpath='',
                       statistic_only=False, analyse_local=False):
    names.sort()
    for name in names:
        downloadFiles(mainpage=mainpage, name=name, sub_side=sub_side, query=query,
                      g_xpath=g_xpath, g_contains=g_contains,
                      f_xpath=f_xpath, f_contains=f_contains, g_part=g_part, f_part=f_part, ext=ext, cookies=cookies,
                      paginator=paginator, name_source=name_source, pretty_print=pretty_print,
                      description_xpath=description_xpath, description_gallery_xpath=description_gallery_xpath,
                      tags_gallery_xpath=tags_gallery_xpath, gallery_overview_info_xpath=gallery_overview_info_xpath,
                      statistic_only=statistic_only, analyse_local=analyse_local)


def downloadFilesFromGallery(mainpage: str, subpage: str, xpath='//a', contains="", part=-1, ext="",
                             cookies: Union[dict, str] = None, name_source: NameSource = NameSource.URL):
    if isinstance(cookies, str):
        cookies = _cookie_string_2_dict(cookies)
    maindest = os.getcwd()
    mainname = _strip_url(mainpage)
    subpage_dirname = subpage.replace('/', '-')
    dest = os.path.join(maindest, mainname, subpage_dirname)
    os.makedirs(dest, exist_ok=True)

    gallery_url = _build_http_path(mainpage, subpage)
    file_urls = get_hrefs(get_response_content(gallery_url, cookies=cookies), xpath, contains)
    download_file_direct(gallery_url, dest, filename="%s.html" % subpage_dirname, cookies=cookies)
    for file_url in file_urls:
        file_url = _createUrl(file_url, mainpage)
        downloadFile(file_url, dest, part=part, ext=ext, cookies=cookies, headers={'Referer': gallery_url}, name_source=name_source)


def firstAndLazyLoaded(mainpage: str, dirname: str, xpath='', contains="", cookies: dict = None):
    maindest = os.getcwd()
    dest = os.path.join(maindest, dirname)
    os.makedirs(dest, exist_ok=True)
    file_urls = get_hrefs(get_response_content(mainpage, cookies=cookies), xpath, contains)
    file_url = file_urls[0]
    for i in range(0, 100):
        contains_sub = contains.replace('0', i.__str__())
        file_url_new = file_url.replace(contains, contains_sub)
        try:
            downloadFile(file_url_new, dest, cookies=cookies, headers={'Referer': mainpage})
        except Exception:
            break


def downloadFile(url: str, dest: str, filename="", part=-1, ext="", cookies: dict = None, headers: dict = None,
                 do_throw=False, name_source: NameSource = NameSource.URL) -> Tuple[Response, str]:
    print(filename)
    if not filename:
        filename = _build_file_name([url], 0, part=part, ext=ext)
    url = _strip_options(url)
    return download_file_direct(url, dest, filename, cookies, headers, do_throw, name_source)


def download_file_direct(url: str, dest: str, filename: str, cookies: dict = None, headers: dict = None,
                         do_throw=False, name_source: NameSource = NameSource.URL) -> Tuple[Response, str]:
    response = get_response(url, cookies, headers, do_throw)
    if response.status_code != 200:
        return response, ""
    if name_source == NameSource.CONTENT:
        response_filename = _extract_filename_from_response(response)
        if response_filename:
            filename = response_filename
    filepath = os.path.join(dest, filename)
    with open(filepath, 'wb') as f:
        f.write(response.content)
    return response, filepath


def get_response_content(url: str, cookies: dict = None, headers: dict = None, do_throw=False) -> bytes:
    response = get_response(url, cookies, headers, do_throw)
    if response.status_code != 200:
        print('bad response: ', response)
        return b''
    return response.content


def get_response(url: str, cookies: dict = None, headers: dict = None, do_throw=False) -> Response:
    if cookies is None:
        cookies = {}
    if headers is None:
        headers = {}
    headers['Connection'] = 'keep-alive'
    print("get: " + url)
    try:
        response = requests.get(url, cookies=cookies, headers=headers)
    except (requests.exceptions.ConnectionError, OSError) as e:
        print("got exception maybe to many requests - try again", e)
        sleep(30)
        response = requests.get(url, cookies=cookies, headers=headers)
    if response.status_code != 200:
        print("error in get " + url + " : " + str(response.status_code) + "" + response.reason)
        if do_throw:
            raise Exception
    return response


def _strip_url(url: str) -> str:
    replacements = ['http://', 'https://', 'www.', '.com', '.de', '.html']
    name = _strip_options(url)
    for replacement in replacements:
        name = name.replace(replacement, '')
    return name


def _build_http_path(mainpage: str, sub_side: str, name: str = "", query="") -> str:
    http_path = ''
    if sub_side:
        http_path += '/' + sub_side
    if name:
        http_path += '/' + name
        if not name.endswith("html"):
            http_path += "/" + query
    return _createUrl(http_path, mainpage)


def _createUrl(url: str, mainpage: str = "") -> str:
    if not url.startswith('http'):
        if mainpage and mainpage.startswith('http'):
            return mainpage + url
        else:
            print("warning: url does not start with http ", url)
    return url


def _build_file_name(file_urls: List[str], file_counter: int, part=-1, ext="", name: str = "", gallery_counter: int = 0,
                     gallery_title: str = "", name_source: NameSource = NameSource.URL) -> str:
    if name_source == NameSource.URL or name_source == NameSource.CONTENT:
        return _url_to_filename(file_urls[file_counter], part, ext)
    filename = ""
    if name_source == NameSource.GALLERY:
        filename = '%03d_%s' % (gallery_counter + 1, gallery_title)
    elif name_source == NameSource.NAME:
        filename = '%s_%03d' % (name, gallery_counter + 1)
    if len(file_urls) > 1:
        return filename + '_%03d' % (file_counter + 1) + ext
    else:
        return filename + ext


def _url_to_filename(url: str, part: int = -1, ext="") -> str:
    filename = _extract_part(url, part)
    if ext:
        filename = filename.rsplit(".", 1)[0] + ext
    if not filename:
        filename = "index.html"
    return filename


def _extract_part(url: str, part: int) -> str:
    url = _strip_options(url)
    return url.split('/')[part]


def _strip_options(url: str) -> str:
    if "?" in url:
        return url[:url.rfind("?")]
    return url


def _extract_filename_from_response(response: Response):
    filename_key = "Content-Disposition"
    if filename_key in response.headers:
        disposition = response.headers[filename_key]
        filename = re.findall(r"filename\*?=([^;]+)", disposition, flags=re.IGNORECASE)
        return filename[0].strip().strip('"')
    return None


def _cookie_string_2_dict(cookie_string: str) -> dict:
    cookie = SimpleCookie()
    cookie.load(cookie_string)

    # Even though SimpleCookie is dictionary-like, it internally uses a Morsel object
    # which is incompatible with requests. Manually construct a dictionary instead.
    cookies = {}
    for key, morsel in cookie.items():
        cookies[key] = morsel.value
    return cookies


def _log_name(html_resolver: HtmlResolver, galleries: List[str],
              html_title: str,
              html_description: List[str]):
    ofilename = os.path.join(html_resolver.dest_main, "download1_names.csv")
    ofile_exists = os.path.isfile(ofilename)
    with open(ofilename, 'a') as ofile:
        if not ofile_exists:
            ofile.write(";".join(
                ["dirname_mainpage", "dirname_name", "number-of-galleries", "download-source-name", "download-title",
                 "download-description", "download-date"]) + "\n")
        ofile.write(";".join(
            [html_resolver.dirname_mainpage, html_resolver.dirname_name, str(len(galleries)), html_resolver.http_path,
             html_title, ", ".join(html_description),
             str(html_resolver.last_date)]) + "\n")


def _log_gallery(html_resolver: HtmlResolver, dirname_gallery: str, filename: str,
                 file_urls: List[str], gallery: str, html_tags: List[str], html_description: List[str],
                 overview_info=""):
    ofilename = os.path.join(html_resolver.dest_main, "download2_galleries.csv")
    ofile_exists = os.path.isfile(ofilename)
    with open(ofilename, 'a') as ofile:
        if not ofile_exists:
            ofile.write(";".join(
                ["dirname_mainpage", "dirname_name", "dirname_gallery", "filename", "number-of-files",
                 "download-source-gallery", "download-date", "html_tags", "html_description", "overview_info"]) + "\n")
        ofile.write(";".join(
            [html_resolver.dirname_mainpage, html_resolver.dirname_name, dirname_gallery, filename, str(len(file_urls)),
             gallery, str(html_resolver.last_date),
             ", ".join(html_tags), ", ".join(html_description), overview_info]) + "\n")


def pretty_name(name: str) -> str:
    parts = name.split('-')
    new_name = ''
    for part in parts:
        new_name += part[0].upper()
        new_name += part[1:]
        new_name += ' '
    return new_name[:-1]


class HtmlHttpResolver(HtmlResolver):
    cookies: dict = None
    headers: dict = None

    def __init__(self, mainpage: str, name: str, sub_side: str = "", query="", pretty_print=False,
                 cookies: Union[dict, str] = None, headers: dict = None):
        super().__init__(mainpage, name, sub_side, query, pretty_print=pretty_print)
        self._set_cookies(cookies)
        self._set_headers(headers)
        os.makedirs(self.dest_name, exist_ok=True)
        os.makedirs(self.dest_html, exist_ok=True)

    def _set_cookies(self, cookies):
        if cookies:
            if isinstance(cookies, str):
                self.cookies = _cookie_string_2_dict(cookies)
            else:
                self.cookies = cookies
        else:
            self.cookies = {}

    def _set_headers(self, headers):
        if headers:
            self.headers = headers
        else:
            self.headers = {}

    def set_referer(self, referer: str = None):
        if referer:
            self.headers['Referer'] = referer
        else:
            del self.headers['Referer']

    def get_mainpage(self) -> bytes:
        self.last_date = datetime.now()
        return get_response_content(self.http_path, cookies=self.cookies, headers=self.headers)

    def get_file(self, url: str, dest: str, filename: str) -> bytes:
        self.last_date = datetime.now()
        response, path = download_file_direct(url, dest, filename, cookies=self.cookies, headers=self.headers)
        if response.status_code != 200:
            print('bad response: ', response)
            return b''
        return response.content


class HtmlFileResolver(HtmlResolver):

    def __init__(self, mainpage: str, name: str, sub_side: str = "", query="", pretty_print=False):
        super().__init__(mainpage, name, sub_side, query, pretty_print=pretty_print)

    def get_mainpage(self) -> bytes:
        filepath = os.path.join(self.dest_html, "%s.html" % self.dirname_name)
        if isfile(filepath):
            self.last_date = modification_date(filepath)
            return read_file_as_bytes(filepath)
        filepath = os.path.join(self.dest_html, "%s_p01.html" % self.dirname_name)
        if isfile(filepath):
            self.last_date = modification_date(filepath)
            return read_file_as_bytes(filepath)
        else:
            print('file not found: ', filepath)
            return b''

    def get_file(self, url: str, dest: str, filename: str) -> bytes:
        filepath = os.path.join(dest, filename)
        if not isfile(filepath):
            print('file not found: ', filepath)
            filepath = os.path.join(dest, filename.replace(' ', '-').lower())
            if not isfile(filepath):
                print('file not found: ', filepath)
                return b''
        self.last_date = modification_date(filepath)
        return read_file_as_bytes(filepath)
