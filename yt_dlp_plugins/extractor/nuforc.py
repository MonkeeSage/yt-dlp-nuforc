import re
import urllib.parse

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    determine_ext,
    float_or_none,
    int_or_none,
    traverse_obj,
    url_or_none,
)


class _SkivBaseIE(InfoExtractor):
    @staticmethod
    def _mpd_url(source_url, regions):
        # The API returns e.g. https://cdn.skiv.com/u/<user>/<fid>/data?v=<token>, but the
        # manifest lives at https://cdn-na.skiv.com/u/<user>/<fid>/videos/dash.mpd?v=<token>
        parsed = urllib.parse.urlparse(source_url)
        path = parsed.path.removesuffix('/data')
        netloc = parsed.netloc
        region = traverse_obj(regions, (0, {str}))
        if region and netloc.startswith('cdn.'):
            netloc = f'cdn-{region}.{netloc.removeprefix("cdn.")}'
        return parsed._replace(netloc=netloc, path=f'{path}/videos/dash.mpd', fragment='').geturl()

    def _download_video_data(self, video_id):
        return self._download_json(
            f'https://skiv.com/api/files/videos/{video_id}', video_id,
            query={'regions': '1'}, note='Downloading video metadata')

    def _extract_video(self, video_id, data):
        source_url = url_or_none(data.get('url'))
        if not source_url:
            raise ExtractorError('Unable to extract video URL', expected=True)

        formats = self._extract_mpd_formats(
            self._mpd_url(source_url, data.get('regions')), video_id, mpd_id='dash')
        for f in formats:
            # Audio BaseURLs are relative ("../audios/..."), which yt-dlp appends without resolving
            f['url'] = re.sub(r'/[^/]+/\.\./', '/', f['url'])

        # The original upload; preferred over the DASH formats since it can be the reporter's
        # full-resolution file with its metadata intact
        formats.append({
            'url': source_url,
            'format_id': 'source',
            'quality': 10,
            **traverse_obj(data, {
                'ext': ('filename', {determine_ext}, {str.lower}),
                'width': ('width', {int_or_none}),
                'height': ('height', {int_or_none}),
                'filesize': ('size', {int_or_none}),
            }),
        })

        return {
            'id': video_id,
            'formats': formats,
            **traverse_obj(data, {
                'title': ('title', {str}),
                'description': ('description', {str}),
                'duration': ('duration', {float_or_none}),
                'timestamp': ('tcreated', {int_or_none}),
                'view_count': ('views', {int_or_none}),
                'age_limit': ('mature', {lambda x: 18 if x else None}),
                'availability': ('visibility', {lambda x: x if x in ('private', 'unlisted') else 'public'}),
            }),
        }


class SkivIE(_SkivBaseIE):
    IE_NAME = 'skiv'
    _VALID_URL = r'https?://(?:www\.)?skiv\.com/(?:v|e|embed)/(?P<id>\w+)'
    _TESTS = [{
        'url': 'https://skiv.com/v/VU87G23',
        'info_dict': {
            'id': 'VU87G23',
            'ext': 'mp4',
            'title': 'S194812 1',
            'duration': 103.44,
            'timestamp': 1766946799,
            'upload_date': '20251228',
            'availability': 'public',
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        return self._extract_video(video_id, self._download_video_data(video_id))


class NuforcIE(_SkivBaseIE):
    IE_NAME = 'nuforc'
    _VALID_URL = r'https?://(?:www\.)?nuforc\.org/sighting/?\?(?:[^#]*&)?id=(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://nuforc.org/sighting/?id=194812',
        'info_dict': {
            'id': 'VU87G23',
            'ext': 'mp4',
            'title': 'NUFORC UFO Sighting 194812',
            'display_id': '194812',
        },
    }, {
        'url': 'https://nuforc.org/sighting/?id=178702',
        'playlist_count': 4,
        'info_dict': {
            'id': '178702',
            'title': 'NUFORC UFO Sighting 178702',
        },
    }]
    # NUFORC's skiv.com channel; videos are titled "S<sighting id> <n>" (filename "S<sighting id>_<n>.<ext>")
    _CHANNEL_ID = '3tk2ZiH'

    def _video_number(self, sighting_id, data):
        return int_or_none(
            traverse_obj(data, ('title', {lambda x: re.fullmatch(rf'S{sighting_id}[ _](\d+)', x.strip())}, 1))
            or traverse_obj(data, ('filename', {lambda x: re.fullmatch(rf'S{sighting_id}_(\d+)\.\w+', x)}, 1)))

    def _real_extract(self, url):
        # nuforc.org itself is behind a Cloudflare challenge, so find the videos via skiv.com search
        sighting_id = self._match_id(url)
        title = f'NUFORC UFO Sighting {sighting_id}'

        results = self._download_json(
            f'https://search.skiv.com/api/search/channel/{self._CHANNEL_ID}', sighting_id,
            query={'q': f'S{sighting_id}'}, note='Searching for sighting videos')

        # The search is not an exact match, so confirm each result belongs to this sighting
        videos = []
        for video_id in traverse_obj(results, (..., 0, {str})):
            data = self._download_video_data(video_id)
            number = self._video_number(sighting_id, data)
            if number is None:
                self.write_debug(f'Skipping {video_id}: {data.get("title")!r} is not from sighting {sighting_id}')
                continue
            videos.append((number, video_id, data))

        if not videos:
            raise ExtractorError(f'No videos found for sighting {sighting_id}', expected=True)
        videos.sort()

        def entry(video_id, data, entry_title):
            return {
                **self._extract_video(video_id, data),
                'title': entry_title,
                'display_id': sighting_id,
                'webpage_url': url,
            }

        if len(videos) == 1:
            _, video_id, data = videos[0]
            return entry(video_id, data, title)

        return self.playlist_result(
            [entry(video_id, data, f'{title} ({number})') for number, video_id, data in videos],
            sighting_id, title)
