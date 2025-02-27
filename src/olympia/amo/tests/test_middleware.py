from django import test
from django.test.client import RequestFactory
from django.urls import reverse

import pytest

from unittest.mock import patch
from pyquery import PyQuery as pq

from olympia.amo.middleware import (
    AuthenticationMiddlewareWithoutAPI,
    RequestIdMiddleware,
)
from olympia.amo.tests import TestCase
from olympia.zadmin.models import Config


pytestmark = pytest.mark.django_db


class TestMiddleware(TestCase):
    def test_no_vary_cookie(self):
        # Requesting / forces a Vary on Accept-Language on User-Agent, since
        # we redirect to /<lang>/<app>/.
        response = test.Client().get('/pages/appversions/')
        assert response['Vary'] == 'Accept-Language, User-Agent'

        # Only Vary on Accept-Encoding after that (because of gzip middleware).
        # Crucially, we avoid Varying on Cookie.
        response = test.Client().get('/pages/appversions/', follow=True)
        assert response['Vary'] == 'Accept-Encoding'

    @patch('django.contrib.auth.middleware.AuthenticationMiddleware.process_request')
    def test_authentication_used_outside_the_api(self, process_request):
        req = RequestFactory().get('/')
        req.is_api = False
        AuthenticationMiddlewareWithoutAPI().process_request(req)
        assert process_request.called

    @patch('django.contrib.sessions.middleware.SessionMiddleware.process_request')
    def test_authentication_not_used_with_the_api(self, process_request):
        req = RequestFactory().get('/')
        req.is_api = True
        AuthenticationMiddlewareWithoutAPI().process_request(req)
        assert not process_request.called

    @patch('django.contrib.auth.middleware.AuthenticationMiddleware.process_request')
    def test_authentication_is_used_with_accounts_auth(self, process_request):
        req = RequestFactory().get('/api/v3/accounts/authenticate/')
        req.is_api = True
        AuthenticationMiddlewareWithoutAPI().process_request(req)
        assert process_request.call_count == 1

        req = RequestFactory().get('/api/v4/accounts/authenticate/')
        req.is_api = True
        AuthenticationMiddlewareWithoutAPI().process_request(req)
        assert process_request.call_count == 2

        req = RequestFactory().get('/api/v5/accounts/authenticate/')
        req.is_api = True
        AuthenticationMiddlewareWithoutAPI().process_request(req)
        assert process_request.call_count == 3


def test_redirect_with_unicode_get():
    response = test.Client().get(
        '/da/firefox/addon/5457?from=/da/firefox/'
        'addon/5457%3Fadvancedsearch%3D1&lang=ja&utm_source=Google+%E3'
        '%83%90%E3%82%BA&utm_medium=twitter&utm_term=Google+%E3%83%90%'
        'E3%82%BA'
    )
    assert response.status_code == 302
    assert 'utm_term=Google+%E3%83%90%E3%82%BA' in response['Location']


def test_source_with_wrong_unicode_get():
    # The following url is a string (bytes), not unicode.
    response = test.Client().get(
        '/firefox/collections/mozmj/autumn/?source=firefoxsocialmedia\x14\x85'
    )
    assert response.status_code == 302
    assert response['Location'].endswith('?source=firefoxsocialmedia%14%C3%82%C2%85')


def test_trailing_slash_middleware():
    response = test.Client().get('/en-US/about/?xxx=\xc3')
    assert response.status_code == 301
    assert response['Location'].endswith('/en-US/about?xxx=%C3%83%C2%83')


class AdminMessageTest(TestCase):
    def test_message(self):
        c = Config.objects.create(key='site_notice', value='ET Sighted.')

        r = self.client.get(reverse('apps.appversions'), follow=True)
        doc = pq(r.content)
        assert doc('#site-notice').text() == 'ET Sighted.'

        c.delete()

        r = self.client.get(reverse('apps.appversions'), follow=True)
        doc = pq(r.content)
        assert len(doc('#site-notice')) == 0


class TestNoDjangoDebugToolbar(TestCase):
    """Make sure the Django Debug Toolbar isn't available when DEBUG=False."""

    def test_no_django_debug_toolbar(self):
        with self.settings(DEBUG=False):
            res = self.client.get(reverse('devhub.index'), follow=True)
            assert b'djDebug' not in res.content
            assert b'debug_toolbar' not in res.content


def test_request_id_middleware(client):
    """Test that we add a request id to every response"""
    response = client.get(reverse('devhub.index'))
    assert response.status_code == 200
    assert isinstance(response['X-AMO-Request-ID'], str)

    # Test that we set `request.request_id` too

    request = RequestFactory().get('/')
    RequestIdMiddleware().process_request(request)
    assert request.request_id
