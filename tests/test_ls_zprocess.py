#####################################################################
#                                                                   #
# /tests/test_ls_zprocess.py                                        #
#                                                                   #
# Copyright 2026, JQI                                               #
# Author: Ian Spielman                                              #
#                                                                   #
# This file is part of labscript-utils, in the labscript suite      #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################
"""A tool's client reaching its server through the shared request protocol."""
import sys
import threading

import pytest

import labscript_utils.ls_zprocess as ls_zprocess
from labscript_utils.ls_zprocess import ZMQClient, ZMQServer


class ShotServer(ZMQServer):
    def handle_add(self, a, b=0):
        return a + b

    def handle_status(self, shot_id):
        return {'shot_42': 'done'}[shot_id]


class ShotClient(ZMQClient):
    server = 'shots'
    # Nothing listens here, so a client that misread the labconfig times out.
    default_port = 1


class LabConfigNamingServer:
    def __init__(self, port):
        self.values = {
            ('servers', 'shots'): 'localhost',
            ('ports', 'shots'): port,
            ('timeouts', 'communication_timeout'): 5,
        }

    def get(self, section, option, fallback=None):
        return self.values.get((section, option), fallback)

    getint = getfloat = get


@pytest.fixture
def client(monkeypatch):
    server = ShotServer()
    monkeypatch.setattr(
        ls_zprocess, 'LabConfig', lambda: LabConfigNamingServer(server.port)
    )
    yield ShotClient()
    server.shutdown()


def test_a_bound_client_reaches_its_servers_handler(client):
    assert client.request('add', 2, b=3) == 5


def test_a_handler_exception_reaches_the_client_and_the_server_goes_on(
    client, monkeypatch
):
    hook_calls = []
    monkeypatch.setattr(sys, 'excepthook', lambda *args: hook_calls.append(args))
    monkeypatch.setattr(threading, 'excepthook', hook_calls.append)
    with pytest.raises(KeyError) as raised:
        client.request('status', 'shot_7')
    assert str(raised.value) == str(KeyError('shot_7'))
    assert client.request('status', 'shot_42') == 'done'
    assert hook_calls == []
