# yt-dlp-nuforc

A [yt-dlp](https://github.com/yt-dlp/yt-dlp) extractor plugin for videos attached to
[NUFORC](https://nuforc.org) sighting reports, e.g. `https://nuforc.org/sighting/?id=194812`.

NUFORC videos are hosted on [skiv.com](https://skiv.com), so this plugin also adds an extractor for
`https://skiv.com/v/<id>` URLs.

## Installation

Requires yt-dlp `2023.01.02` or above.

### Installing yt-dlp with pipx

Fresh install:

```
pipx install 'yt-dlp[default]'
```

To upgrade an existing pipx install in place (this keeps any injected plugins):

```
pipx runpip yt-dlp install --upgrade 'yt-dlp[default]'
```

Add `--pre` to that command to get yt-dlp's nightly pre-releases instead of the latest stable release.

This plugin never requests nuforc.org itself (see [How it works](#how-it-works)), so it does not need
browser cookies, a custom user agent, or the `curl-cffi` impersonation extra.

### Installing the plugin with pipx

Inject the plugin into yt-dlp's pipx environment:

```
pipx inject yt-dlp git+https://github.com/MonkeeSage/yt-dlp-nuforc.git
```

or from a local checkout:

```
pipx inject yt-dlp /path/to/yt-dlp-nuforc
```

### pip

```
python3 -m pip install -U git+https://github.com/MonkeeSage/yt-dlp-nuforc.git
```

### Other

See the yt-dlp [plugin installation docs](https://github.com/yt-dlp/yt-dlp#installing-plugins).

## Usage

```
yt-dlp 'https://nuforc.org/sighting/?id=194812'
yt-dlp -F 'https://nuforc.org/sighting/?id=194812'
```

Videos are titled `NUFORC UFO Sighting <id>`. Sightings with more than one video come back as a
playlist, with entries titled `NUFORC UFO Sighting <id> (<n>)`.

### Formats

By default the `source` format is downloaded: the original file uploaded to skiv.com. It may be the
reporter's own video at full resolution with its metadata preserved, though newer reports are often
re-encoded by NUFORC with a watermark added and the metadata reset.

skiv.com's re-encoded DASH streams (separate video and audio, 240p to 1080p) are also available.
List everything with `-F` and select DASH streams with `-f`, for example:

```
yt-dlp -f 'bv+ba' 'https://nuforc.org/sighting/?id=194812'                  # best DASH video + audio
yt-dlp -f 'bv[height<=720]+ba' 'https://nuforc.org/sighting/?id=194812'     # DASH video up to 720p
yt-dlp -f 'dash-3+dash-5' 'https://nuforc.org/sighting/?id=194812'          # specific format IDs from -F
```

## How it works

nuforc.org is behind a Cloudflare challenge, so the plugin only uses the sighting ID from the URL and
gets everything else from skiv.com:

1. NUFORC's skiv.com channel (`3tk2ZiH`) titles each video `S<sighting id> <n>`. The channel is searched with
   `https://search.skiv.com/api/search/channel/3tk2ZiH?q=S<sighting id>`, which returns the skiv video IDs.
2. `https://skiv.com/api/files/videos/<video id>?regions=1` returns each video's metadata, including a `url`
   such as `https://cdn.skiv.com/u/<user>/<fid>/data?v=<token>`. Search results whose title (or filename)
   doesn't exactly match the sighting are dropped, and the rest are ordered by `<n>`.
3. The DASH manifest is fetched from `https://cdn-<region>.skiv.com/u/<user>/<fid>/videos/dash.mpd?v=<token>`,
   and its video and audio representations become the available formats.
