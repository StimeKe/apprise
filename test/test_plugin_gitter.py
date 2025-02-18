# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import pytest
from unittest import mock

import requests

from apprise.plugins.NotifyGitter import NotifyGitter
from helpers import AppriseURLTester

from json import dumps
from datetime import datetime
from datetime import timezone

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyGitter
    ##################################
    ('gitter://', {
        'instance': TypeError,
    }),
    ('gitter://:@/', {
        'instance': TypeError,
    }),
    # Invalid Token Length
    ('gitter://%s' % ('a' * 12), {
        'instance': TypeError,
    }),
    # Token specified but no channel
    ('gitter://%s' % ('a' * 40), {
        'instance': TypeError,
    }),
    # Token + channel
    ('gitter://%s/apprise' % ('b' * 40), {
        'instance': NotifyGitter,
        'response': False,
    }),
    # include image in post
    ('gitter://%s/apprise?image=Yes' % ('c' * 40), {
        'instance': NotifyGitter,
        'response': False,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'gitter://c...c/apprise',
    }),
    # Don't include image in post (this is the default anyway)
    ('gitter://%s/apprise?image=Yes' % ('d' * 40), {
        'instance': NotifyGitter,
        'response': False,
        # don't include an image by default
        'include_image': False,
    }),
    # Don't include image in post (this is the default anyway)
    ('gitter://%s/apprise?image=No' % ('e' * 40), {
        'instance': NotifyGitter,
        'response': False,
    }),
    ('gitter://%s/apprise' % ('f' * 40), {
        'instance': NotifyGitter,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('gitter://%s/apprise' % ('g' * 40), {
        'instance': NotifyGitter,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('gitter://%s/apprise' % ('h' * 40), {
        'instance': NotifyGitter,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_gitter_urls():
    """
    NotifyGitter() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_gitter_general(mock_post, mock_get):
    """
    NotifyGitter() General Tests

    """

    # Generate a valid token (40 characters)
    token = 'a' * 40

    response_obj = [
        {
            'noindex': False,
            'oneToOne': False,
            'avatarUrl': 'https://path/to/avatar/url',
            'url': '/apprise-notifications/community',
            'public': True,
            'tags': [],
            'lurk': False,
            'uri': 'apprise-notifications/community',
            'lastAccessTime': '2019-03-25T00:12:28.144Z',
            'topic': '',
            'roomMember': True,
            'groupId': '5c981cecd73408ce4fbbad2f',
            'githubType': 'REPO_CHANNEL',
            'unreadItems': 0,
            'mentions': 0,
            'security': 'PUBLIC',
            'userCount': 1,
            'id': '5c981cecd73408ce4fbbad31',
            'name': 'apprise/community',
        },
    ]

    # Epoch time:
    epoch = datetime.fromtimestamp(0, timezone.utc)

    request = mock.Mock()
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok
    request.headers = {
        'X-RateLimit-Reset': (
            datetime.now(timezone.utc) - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }

    # Prepare Mock
    mock_get.return_value = request
    mock_post.return_value = request

    # Variation Initializations
    obj = NotifyGitter(token=token, targets='apprise')
    assert isinstance(obj, NotifyGitter) is True
    assert isinstance(obj.url(), str) is True

    # apprise room was found
    assert obj.send(body="test") is True

    # Change our status code and try again
    request.status_code = 403
    assert obj.send(body="test") is False
    assert obj.ratelimit_remaining == 1

    # Return the status
    request.status_code = requests.codes.ok
    # Force a reset
    request.headers['X-RateLimit-Remaining'] = 0
    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    request.headers['X-RateLimit-Remaining'] = 10
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Handle cases where we simply couldn't get this field
    del request.headers['X-RateLimit-Remaining']
    assert obj.send(body="test") is True
    # It remains set to the last value
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    request.headers['X-RateLimit-Remaining'] = 1

    # Handle cases where our epoch time is wrong
    del request.headers['X-RateLimit-Reset']
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers['X-RateLimit-Reset'] = \
        (datetime.now(timezone.utc) - epoch).total_seconds() + 1
    request.headers['X-RateLimit-Remaining'] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers['X-RateLimit-Reset'] = \
        (datetime.now(timezone.utc) - epoch).total_seconds() - 1
    request.headers['X-RateLimit-Remaining'] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our limits to always work
    request.headers['X-RateLimit-Reset'] = \
        (datetime.now(timezone.utc) - epoch).total_seconds()
    request.headers['X-RateLimit-Remaining'] = 1
    obj.ratelimit_remaining = 1

    # Cause content response to be None
    request.content = None
    assert obj.send(body="test") is True

    # Invalid JSON
    request.content = '{'
    assert obj.send(body="test") is True

    # Return it to a parseable string
    request.content = '{}'

    # Support the 'to' as a target
    results = NotifyGitter.parse_url(
        'gitter://{}?to={}'.format(token, 'apprise'))
    assert isinstance(results, dict) is True
    assert 'apprise' in results['targets']

    # cause a json parsing issue now
    response_obj = None
    assert obj.send(body="test") is True

    response_obj = '{'
    assert obj.send(body="test") is True

    # Variation Initializations
    obj = NotifyGitter(token=token, targets='apprise')
    assert isinstance(obj, NotifyGitter) is True
    assert isinstance(obj.url(), str) is True
    # apprise room was not found
    assert obj.send(body="test") is False

    # Test exception handling
    mock_post.side_effect = \
        requests.ConnectionError(0, 'requests.ConnectionError()')

    # Create temporary _room_mapping object so we will find the apprise
    # channel on our second call to send()
    obj._room_mapping = {
        'apprise': {
            'id': '5c981cecd73408ce4fbbad31',
            'uri': 'apprise-notifications/community',
        }
    }
    assert obj.send(body='test body', title='test title') is False


def test_plugin_gitter_edge_cases():
    """
    NotifyGitter() Edge Cases

    """
    # Define our channels
    targets = ['apprise']

    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        NotifyGitter(token=None, targets=targets)
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyGitter(token="   ", targets=targets)
