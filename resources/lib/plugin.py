# -*- coding: utf-8 -*-
import logging
import xbmcaddon
from . import kodilogging
from . import kodiutils
from . import settings

import sys

from urllib import urlencode
from urllib import quote
from urlparse import parse_qsl

from datetime import datetime

import xbmcgui
import xbmcplugin
import xbmc

import requests
import itertools
import operator

import time

ADD_ON = xbmcaddon.Addon()
logger = logging.getLogger(ADD_ON.getAddonInfo('id'))
kodilogging.config(logger)


class Zee5Plugin(object):
    ITEMS_LIMIT = 25

    def __init__(self, plugin_args):
        # Get the plugin url in plugin:// notation.
        self.plugin_url = plugin_args[0]
        # Get the plugin handle as an integer number.
        self.handle = int(plugin_args[1])
        # Parse a URL-encoded paramstring to the dictionary of
        # {<parameter>: <value>} elements
        self.params = dict(parse_qsl(plugin_args[2][1:]))

        # Static data
        self.platform = 'web_app'
        self.languages = settings.get_languages()
        self.session = requests.Session()

        # Initialise the token.
        self.token = self.params['token'] if 'token' in self.params else self._get_token()

    def _get_headers(self):
        headers = {
            "Origin": "https://www.zee5.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.80 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://www.zee5.com",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if hasattr(self, 'token'):
            headers["X-ACCESS-TOKEN"] = self.token

        return headers

    def _get_video_token(self):
        data = self.make_request('https://useraction.zee5.com/tokennd/')
        return data['video_token']

    def _get_token(self):
        data = self.make_request(
            'https://useraction.zee5.com/token/platform_tokens.php?platform_name={}'.format(self.platform)
        )
        return data['token']

    def list_season(self, season_id, season_name):
        # Set plugin category. It is displayed in some skins as the name
        # of the current section.
        xbmcplugin.setPluginCategory(self.handle, season_name)

        data = self.make_request("https://gwapi.zee5.com/content/season/{}".format(season_id))
        for episode in data['episode']:
            self.add_video_item(episode)

        self.add_search_item()

        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_NONE)
        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_show(self, show_id, show_name):
        # Set plugin category. It is displayed in some skins as the name
        # of the current section.
        xbmcplugin.setPluginCategory(self.handle, show_name)

        data = self.make_request("https://gwapi.zee5.com/content/tvshow/{}".format(show_id))
        for season in data['seasons']:
            self.add_directory_item(
                content_id=season['id'],
                title=season['title'],
                description=season.get('description'),
                action='season',
                parent_title=show_name,
                item=season
            )

        self.add_search_item()

        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_NONE)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_manual(self, manual_id, page_number, manual_name):
        # Set plugin category. It is displayed in some skins as the name
        # of the current section.
        xbmcplugin.setPluginCategory(self.handle, manual_name)

        data = self.make_request(
            'https://gwapi.zee5.com/content/collection/{id}?page={page}&limit={limit}&languages={lang}&translation=en&version=3'.format(
                id=manual_id,
                page=page_number,
                limit=Zee5Plugin.ITEMS_LIMIT,
                lang=self.languages
            )
        )

        for item in data['buckets'][0]['items']:
            # {
            #      "id": "0-0-16460",
            #      "rating": 5,
            #      "duration": 183,
            #      "content_owner": "Zee Entertainment Enterprises Ltd",
            #      "business_type": "free",
            #      "genre": [
            #          {
            #              "id": "Drama",
            #              "value": "Drama"
            #          }
            #      ],
            #      "title": "Cabaret - Trailer",
            #      "age_rating": "U",
            #      "tags": [
            #          "Cabaret"
            #      ],
            #      "asset_type": 0,
            #      "original_title": "Cabaret - Trailer",
            #      "asset_subtype": "trailer",
            #      "video": [
            #          "/drm1/PRIORITY1080/PROMOS/December/30122018/CABARET_PF_1.mp4/manifest.mpd"
            #      ],
            #      "orderid": 0,
            #      "description": "Cabaret is A ZEE5 Original Film, starring Richa Chadda & Gulshan Devaiah, directed by Kaustav Narayan Niyogi premieres 9th January on ZEE5.",
            #      "genres": [
            #          {
            #              "id": "Drama",
            #              "value": "Drama"
            #          }
            #      ],
            #      "image_url": {
            #          "list": "https://akamaividz.zee5.com/resources/0-0-16460/list/270x152/cabarettrailer1170x658.jpg",
            #          "cover": "https://akamaividz1.zee5.com/resources/0-0-16460/cover/270x405/cabarettrailer1920x770.jpg"
            #      },
            # },
            subtype = item.get('asset_subtype')
            if subtype == 'Manual':
                self.add_directory_item(
                    content_id=item['id'],
                    title=item['title'],
                    description=item.get('description'),
                    action='manual',
                    parent_title=manual_name,
                    item=item
                )

            elif subtype in [
                'trailer', 'movie', 'video',
                'episode', 'teaser', 'music',
                'webisode', 'clip', 'preview',
                'news'
            ]:
                self.add_video_item(item)

            elif subtype in ['original', 'tvshow']:
                self.add_directory_item(
                    content_id=item['id'],
                    title=item['title'],
                    description=item.get('description'),
                    action='show',
                    parent_title=manual_name,
                    item=item
                )

            elif subtype not in ['external_link']:
                logger.warn(u'Skipping rendering sub-type from item - {}: {}'.format(subtype, item))

        self.add_next_page_and_search_item(
            item=data, original_title=manual_name, action='manual'
        )

        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_NONE)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_collection(self, collection_id, page_number, collection_name):
        # Set plugin category. It is displayed in some skins as the name
        # of the current section.
        xbmcplugin.setPluginCategory(self.handle, collection_name)

        data = self.make_request(
            'https://gwapi.zee5.com/content/collection/{id}?page={page}&limit={limit}&item_limit=1&languages={lang}&version=3'.format(
                id=collection_id,
                page=page_number,
                limit=Zee5Plugin.ITEMS_LIMIT,
                lang=self.languages,
            )
        )
        for bucket in data['buckets'] or []:
            # {
            #      "id": "0-8-manualcol_1053401488",
            #      "asset_type": 8,
            #      "asset_subtype": "Manual",
            #      "title": "Trending",
            #      "original_title": "Trending",
            #      "description": "Home Page Slider",
            #      "short_description": "Home Page Slider",
            #      "tags": [
            #          "banner"
            #      ],
            #      "age_rating": "",
            #      "rating": 0,
            #      "image": {
            #          "app_cover": "",
            #          "list": "",
            #          "cover": "",
            #          "tv_cover": ""
            #      },
            #      "image_url": {
            #          "list": "",
            #          "cover": ""
            #      },
            #      "audio_languages": [],
            #      "seo_title": "",
            #      "release_date": "",
            #      "content_owner": "",
            #      "countries": [
            #          "IN"
            #      ],
            #      "items": []
            #      "total": 24
            # },

            # Skip buckets without any items.
            if not bucket.get('items'):
                continue

            self.add_directory_item(
                content_id=bucket['id'],
                title=bucket['title'],
                description=bucket.get('description'),
                action='manual',
                parent_title=collection_name,
                item=bucket,
            )

        self.add_next_page_and_search_item(
            item=data, original_title=collection_name, action='collection'
        )

        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_NONE)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    def list_collections(self):
        # Set plugin category. It is displayed in some skins as the name
        # of the current section.
        xbmcplugin.setPluginCategory(self.handle, 'Collections')

        data = self.make_request('https://b2bapi.zee5.com/front/countrylist.php?lang=en&ccode=CA')
        for name, collection_id in data[0]['collections'][self.platform].iteritems():
            # "web_app": {
            #     "home": "0-8-homepage",
            #     "tvshows": "0-8-tvshows",
            #     "videos": "0-8-videos",
            #     "movies": "0-8-movies",
            #     "originals": "0-8-zeeoriginals",
            #     "premium": "0-8-premiumcontents",
            #     "news": "0-8-626"
            # },
            self.add_directory_item(
                title=name.title(),
                content_id=collection_id,
                description=name.title(),
                action='collection',
            )

        self.add_search_item()

        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)

        # Finish creating a virtual folder.
        xbmcplugin.endOfDirectory(self.handle)

    @staticmethod
    def get_user_input():
        kb = xbmc.Keyboard('', 'Search for Movies/TV Shows/Trailers/Videos in all languages')
        kb.doModal()  # Onscreen keyboard appears
        if not kb.isConfirmed():
            return

        # User input
        return kb.getText()

    def list_search(self):
        query = Zee5Plugin.get_user_input()
        if not query:
            return []

        # Set plugin category. It is displayed in some skins as the name
        # of the current section.
        xbmcplugin.setPluginCategory(self.handle, 'Search/{}'.format(query))

        url = 'https://gwapi.zee5.com/content/getContent/autoSuggest?q={}&limit={}&translation=en&languages=hi,ta,en&country=CA&version=1'.format(
            quote(query),
            Zee5Plugin.ITEMS_LIMIT
        )
        data = self.make_request(url)
        if not data.get('numFound'):
            kodiutils.notification('No Search Results', 'No item found for {}'.format(query))
            return

        for item in data['docs']:
            self.add_video_item(item)

        # Add a sort method for the virtual folder items (alphabetically, ignore articles)
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_NONE)
        xbmcplugin.endOfDirectory(self.handle)

    def make_request(self, url):
        logger.info("Making request: {}".format(url))
        response = self.session.get(url, headers=self._get_headers(), cookies=self.session.cookies)
        assert response.status_code == 200
        return response.json()

    @staticmethod
    def get_genre(item):
        """
        Returns a string of genre -- comma separated if multiple genres.
        Returns ALL as default.
        """
        if not item:
            return 'ALL'

        genres = set()
        for genreField in ['genre', 'genres']:
            data = item.get(genreField)
            if not data:
                continue
            genres.update(itertools.imap(operator.itemgetter('value'), data))

        return ",".join(list(genres)) if genres else 'ALL'

    @staticmethod
    def get_images(item):
        """
        Returns a tuple of list_image & cover_image.
        """
        images = item.get('image_url')
        if not images:
            return None, None

        if type(images) is dict:
            return images.get('list'), images.get('cover')
        else:
            return images, images

    def add_video_item(self, video):
        # Create a list item with a text label and a thumbnail image.
        episode_no = video.get('episode_number')
        title = video['title']
        list_item = xbmcgui.ListItem(label=title)

        # Set additional info for the list item.
        episode_date = video.get('release_date')
        if episode_date:
            try:
                episode_date = datetime(
                    *(time.strptime(episode_date.split('T')[0], "%Y-%m-%d")[0:6])
                )
            except Exception as e:
                logger.warn('Failed to parse the episode date - {} -- {}'.format(episode_date, str(e)))
                episode_date = None
                pass

        list_item.setInfo('video', {
            'title': title,
            'genre': Zee5Plugin.get_genre(video),
            'episode': episode_no,
            'plot': video.get('description'),
            'duration': video.get('duration'),
            'year': episode_date.year if episode_date else None,
            'date': episode_date.strftime('%d.%m.%Y') if episode_date else None,
            'mediatype': 'video',
        })

        # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
        # Here we use the same image for all items for simplicity's sake.
        list_image, cover_image = Zee5Plugin.get_images(video)
        list_item.setArt({
            'thumb': list_image or cover_image,
            'icon': list_image or cover_image,
            'fanart': cover_image or list_image,
        })

        # Set 'IsPlayable' property to 'true'.
        # This is mandatory for playable items!
        list_item.setProperty('IsPlayable', 'true')

        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=play&video=http:
        # //www.vidsplay.com/wp-content/uploads/2017/04/crab.mp4
        url = self.get_url(action='play', content_id=video['id'])

        # Add the list item to a virtual Kodi folder.
        # is_folder = False means that this item won't open any sub-list.
        is_folder = False

        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(self.handle, url, list_item, is_folder)

    def add_directory_item(
        self,
        title,
        description,
        content_id,
        action,
        parent_title='',
        item=None,
    ):
        # Create a list item with a text label and a thumbnail image.
        list_item = xbmcgui.ListItem(label=title)

        # Set graphics (thumbnail, fanart, banner, poster, landscape etc.) for the list item.
        # Here we use the same image for all items for simplicity's sake.
        # In a real-life plugin you need to set each image accordingly.
        if item and item.get('image_url'):
            list_image, cover_image = Zee5Plugin.get_images(item)
            list_item.setArt({
                'thumb': list_image or cover_image,
                'icon': list_image or cover_image,
                'fanart': cover_image or list_image
            })

        # Set additional info for the list item.
        # Here we use a category name for both properties for for simplicity's sake.
        # setInfo allows to set various information for an item.
        # For available properties see the following link:
        # https://codedocs.xyz/xbmc/xbmc/group__python__xbmcgui__listitem.html#ga0b71166869bda87ad744942888fb5f14
        # 'mediatype' is needed for a skin to display info for this ListItem correctly.
        list_item.setInfo('video', {
            'count': content_id,
            'title': title,
            'genre': self.get_genre(item),
            'plot': description,
            'mediatype': 'video'
        })

        # Create a URL for a plugin recursive call.
        # Example: plugin://plugin.video.example/?action=listing&category=Animals
        url = self.get_url(
            action=action,
            content_id=content_id,
            title=u'{}/{}'.format(parent_title, title) if parent_title else title,
        )

        # is_folder = True means that this item opens a sub-list of lower level items.
        is_folder = True

        # Add our item to the Kodi virtual folder listing.
        xbmcplugin.addDirectoryItem(self.handle, url, list_item, is_folder)

    def add_next_page_and_search_item(self, item, original_title, action):
        if item.get('page', 0) * item.get('limit', 0) < item.get('total', 0):
            title = '| Next Page >>>'
            list_item = xbmcgui.ListItem(label=title)
            list_item.setInfo('video', {
                'mediatype': 'video'
            })

            # Create a URL for a plugin recursive call.
            # Example: plugin://plugin.video.example/?action=listing&category=Animals
            url = self.get_url(
                action=action,
                content_id=item['id'],
                page_number=item['page'] + 1,
                title=original_title
            )

            # is_folder = True means that this item opens a sub-list of lower level items.
            is_folder = True

            # Add our item to the Kodi virtual folder listing.
            xbmcplugin.addDirectoryItem(self.handle, url, list_item, is_folder)

        # Add Search item.
        self.add_search_item()

    def add_search_item(self):
        self.add_directory_item(
            title='| Search', content_id=1, description='Search', action='search'
        )

    @staticmethod
    def safe_string(content):
        import unicodedata

        if not content:
            return content

        if isinstance(content, unicode):
            content = unicodedata.normalize('NFKD', content).encode('ascii', 'ignore')

        return content

    def get_url(self, **kwargs):
        """
        Create a URL for calling the plugin recursively from the given set of keyword arguments.

        :param kwargs: "argument=value" pairs
        :type kwargs: dict
        :return: plugin call URL
        :rtype: str
        """
        valid_kwargs = {
            key: Zee5Plugin.safe_string(value)
            for key, value in kwargs.iteritems()
            if value is not None
        }
        valid_kwargs['token'] = self.token
        return '{0}?{1}'.format(self.plugin_url, urlencode(valid_kwargs))

    def play_video(self, item_id):
        """
        Play a video by the provided path.
        """
        def get_subtitles(item):
            _subtitles = item['video_details'].get('subtitles')
            if not _subtitles:
                return []

            url = item['video_details'].get('url')
            subtitles_files = []
            for subtitle_lang in _subtitles:
                if not subtitle_lang:
                    continue

                # https://zee5vod.akamaized.net/drm/PRIORITY1080/TELUGU_MOVIES/
                # GEETHA_GOVINDAM_TELUGU_MOVIE_te.mp4/manifest-en.vtt
                subtitle_url = "https://zee5vod.akamaized.net{}".format(
                    url.replace(
                        '/manifest.mpd', '/manifest-{}.vtt'.format(subtitle_lang)
                    )
                )
                subtitle_file = kodiutils.download_url_content_to_temp(subtitle_url, '{}-{}.srt'.format(
                    Zee5Plugin.safe_string(item['title']),
                    subtitle_lang,
                ))
                subtitles_files.append(subtitle_file)

            return subtitles_files

        def get_video_url(item):
            hls_url = item['video_details']['hls_url']
            if not hls_url:
                kodiutils.notification(
                    "Video URL missing!", "Missing video URL for {}".format(data.get('title')),
                )
                return

            token = self._get_video_token()
            # PRIORITY1080/PROMOS/December/13122018/WhatsupVel_Trailer_WN_PF_13122018NEW.mp4/
            # index.m3u8?token
            return 'https://zee5vodnd.akamaized.net/{url}{token}'.format(
                url=hls_url.replace('/drm', '/hls'),
                token=token
            )

        data = self.make_request('https://gwapi.zee5.com/content/details/{}?translation=en'.format(item_id))
        video_url = get_video_url(data)
        if not video_url:
            return

        subtitles = get_subtitles(data)

        logger.debug('Playing video: {}, subtitles: {}'.format(video_url, subtitles))
        # Create a playable item with a path to play.
        cover_image, _ = self.get_images(data)
        play_item = xbmcgui.ListItem(
            path=video_url,
            iconImage=cover_image,
            thumbnailImage=cover_image,
        )
        if subtitles:
            play_item.setSubtitles(subtitles)

        # Pass the item to the Kodi player.
        xbmcplugin.setResolvedUrl(self.handle, True, listitem=play_item)

    def router(self):
        """
        Main routing function which parses the plugin param string and handles it appropirately.
        """
        # Check the parameters passed to the plugin
        logger.info('Handling route params -- {}'.format(self.params))
        if self.params:
            action = self.params.get('action')
            content_id = self.params.get('content_id')
            title = self.params.get('title')
            page_number = self.params.get('page_number', 1)

            if action == 'collection':
                self.list_collection(content_id, page_number, title)

            elif action == 'manual':
                self.list_manual(content_id, page_number, title)

            elif action == 'show':
                self.list_show(content_id, title)

            elif action == 'season':
                self.list_season(content_id, title)

            elif action == 'play':
                self.play_video(content_id)

            elif action == 'search':
                self.list_search()

            else:
                # If the provided paramstring does not contain a supported action
                # we raise an exception. This helps to catch coding errors,
                # e.g. typos in action names.
                raise ValueError('Invalid paramstring: {0}!'.format(self.params))

        else:
            # List all the channels at the base level.
            self.list_collections()


def run():
    # Initial stuffs.
    kodiutils.cleanup_temp_dir()

    # Call the router function and pass the plugin call parameters to it.
    # We use string slicing to trim the leading '?' from the plugin call paramstring
    Zee5Plugin(sys.argv).router()
