import re

from pyquery import PyQuery as pq
from urllib.parse import urlparse, parse_qs

from pollbot.exceptions import TaskError
from pollbot.utils import build_version_id, Channel, get_version_channel
from . import get_session, heartbeat_factory


async def get_releases(product):
    with get_session() as session:
        url = 'https://www.mozilla.org/en-US/{}/releases/'.format(product)
        async with session.get(url) as resp:
            if resp.status != 200:
                msg = 'Releases page not available  ({})'.format(resp.status)
                raise TaskError(msg)
            body = await resp.text()
            d = pq(body)
            major_releases = [n.text for n in d("strong>a")]
            minor_releases = [n.text for n in d("ol>li>ol>li>a")]
            return sorted(major_releases + minor_releases, key=build_version_id)


async def release_notes(product, version):
    channel = get_version_channel(version)
    if channel is Channel.BETA:
        parts = version.split('b')
        version = "{}beta".format(parts[0])
    elif channel is Channel.ESR:
        version = re.sub('esr$', '', version)

    url = 'https://www.mozilla.org/en-US/{}/{}/releasenotes/'.format(product, version)

    with get_session() as session:
        async with session.get(url) as resp:
            return resp.status != 404


async def security_advisories(product, version):
    channel = get_version_channel(version)
    # Security advisories are always present for BETA and NIGHTLY
    # because we don't publish any.
    if channel in (Channel.BETA, Channel.NIGHTLY):
        return True

    with get_session() as session:
        url = 'https://www.mozilla.org/en-US/security/known-vulnerabilities/{}/'.format(product)
        async with session.get(url) as resp:
            if resp.status != 200:
                msg = 'Security advisories page not available  ({})'.format(resp.status)
                raise TaskError(msg)
            # Does the content contains the version number?
            body = await resp.text()
            d = pq(body)

            if channel is Channel.ESR:
                version = re.sub('esr$', '', version)
                last_release = d("html").attr('data-esr-versions')
            else:
                last_release = d("html").attr('data-latest-firefox')
            return build_version_id(last_release) >= build_version_id(version)


async def download_links(product, version):
    channel = get_version_channel(version)
    if channel in (Channel.ESR, Channel.RELEASE):
        url = 'https://www.mozilla.org/en-US/{}/all/'.format(product)
    else:
        url = 'https://www.mozilla.org/fr/firefox/channel/desktop/'

    with get_session() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                msg = 'Download page not available  ({})'.format(resp.status)
                raise TaskError(msg)
            body = await resp.text()
            d = pq(body)

            if channel is Channel.BETA:
                link_path = "#desktop-beta-download > .download-list > .os_linux64 > a"
                url = d(link_path).attr('href')
                qs = parse_qs(urlparse(url).query)
                product_parts = qs["product"][0].split('-')
                last_release = product_parts[1]
            elif channel is Channel.ESR:
                version = re.sub('esr$', '', version)
                last_release = d("html").attr('data-esr-versions')
            else:
                # Does the content contains the version number?
                last_release = d("html").attr('data-latest-firefox')

            return build_version_id(last_release) >= build_version_id(version)


heartbeat = heartbeat_factory('https://www.mozilla.org/en-US/firefox/all/')
