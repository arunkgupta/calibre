#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
store_version = 11  # Needed for dynamic plugin loading

from contextlib import closing
import urllib

from lxml import html

from PyQt5.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult

SEARCH_BASE_URL = 'http://www.amazon.fr/s/'
SEARCH_BASE_QUERY = {'url': 'search-alias=digital-text'}
BY = 'de'
KINDLE_EDITION = 'Format Kindle'
DETAILS_URL = 'http://amazon.fr/dp/'
STORE_LINK =  'http://www.amazon.fr'
DRM_SEARCH_TEXT = 'Simultaneous Device Usage'
DRM_FREE_TEXT = 'Unlimited'

def search_amazon(query, max_results=10, timeout=60,
                  write_html_to=None,
                  base_url=SEARCH_BASE_URL,
                  base_query=SEARCH_BASE_QUERY,
                  field_keywords='field-keywords'
                  ):
    uquery = base_query.copy()
    uquery[field_keywords] = query
    def asbytes(x):
        if isinstance(x, type('')):
            x = x.encode('utf-8')
        return x
    uquery = {asbytes(k):asbytes(v) for k, v in uquery.iteritems()}
    url = base_url + '?' + urllib.urlencode(uquery).decode('ascii')
    br = browser()

    counter = max_results
    with closing(br.open(url, timeout=timeout)) as f:
        raw = f.read()
        if write_html_to is not None:
            with open(write_html_to, 'wb') as f:
                f.write(raw)
        doc = html.fromstring(raw)
        try:
            results = doc.xpath('//div[@id="atfResults" and @class]')[0]
        except IndexError:
            return

        if 's-result-list-parent-container' in results.get('class', ''):
            data_xpath = "descendant-or-self::li[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-result-item ')]"
            format_xpath = './/a[@title="%s"]/@title' % KINDLE_EDITION
            asin_xpath = '@data-asin'
            cover_xpath =  "descendant-or-self::img[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-access-image ')]/@src"
            title_xpath = "descendant-or-self::h2[@class and contains(concat(' ', normalize-space(@class), ' '), ' s-access-title ')]//text()"
            author_xpath = './/span[starts-with(text(), "%s ")]/following-sibling::span//text()' % BY
            price_xpath = '(.//span[contains(@class, " s-price ")])[last()]//text()'
        else:
            return

        for data in doc.xpath(data_xpath):
            if counter <= 0:
                break

            # Even though we are searching digital-text only Amazon will still
            # put in results for non Kindle books (author pages). Se we need
            # to explicitly check if the item is a Kindle book and ignore it
            # if it isn't.
            format = ''.join(data.xpath(format_xpath))
            if 'kindle' not in format.lower():
                continue

            # We must have an asin otherwise we can't easily reference the
            # book later.
            asin = data.xpath(asin_xpath)
            if asin:
                asin = asin[0]
            else:
                continue

            cover_url = ''.join(data.xpath(cover_xpath))

            title = ''.join(data.xpath(title_xpath))
            author = ''.join(data.xpath(author_xpath))
            try:
                author = author.split('by ', 1)[1].split(" (")[0]
            except:
                pass

            price = ''.join(data.xpath(price_xpath))

            counter -= 1

            s = SearchResult()
            s.cover_url = cover_url.strip()
            s.title = title.strip()
            s.author = author.strip()
            s.price = price.strip()
            s.detail_item = asin.strip()
            s.formats = 'Kindle'

            yield s

class AmazonKindleStore(StorePlugin):

    def open(self, parent=None, detail_item=None, external=False):
        store_link = (DETAILS_URL + detail_item) if detail_item else STORE_LINK
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        for result in search_amazon(query, max_results=max_results, timeout=timeout):
            yield result

    def get_details(self, search_result, timeout):
        url = DETAILS_URL

        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            if idata.xpath('boolean(//div[@class="content"]//li/b[contains(text(), "' +
                           DRM_SEARCH_TEXT + '")])'):
                if idata.xpath('boolean(//div[@class="content"]//li[contains(., "' +
                               DRM_FREE_TEXT + '") and contains(b, "' +
                               DRM_SEARCH_TEXT + '")])'):
                    search_result.drm = SearchResult.DRM_UNLOCKED
                else:
                    search_result.drm = SearchResult.DRM_UNKNOWN
            else:
                search_result.drm = SearchResult.DRM_LOCKED
        return True

if __name__ == '__main__':
    import sys
    for result in search_amazon(' '.join(sys.argv[1:]), write_html_to='/t/amazon.html'):
        print (result)
