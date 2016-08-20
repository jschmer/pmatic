#!/usr/bin/env python
# encoding: utf-8
#
# pmatic - Python API for Homematic. Easy to use.
# Copyright (C) 2016 Lars Michelsen <lm@larsmichelsen.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Provides the XMP-API interface to the CCU

This module provides you with the low level API of pmatic to the CCU.
Low level API means that it cares about connecting to the interfaces on
the CCU, authenticates with it and accesses the API calls and makes them
all available in the Python code. So that you can simply call methods on
the API object to make API calls and get Python data structures back.
"""

# Add Python 3.x behaviour to 2.7
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import threading

try:
    from xmlrpclib import ServerProxy, ProtocolError, Fault
except ImportError:
    from xmlrpc.client import ServerProxy, ProtocolError, Fault

from pmatic.exceptions import PMException, PMConnectionError
import pmatic.utils as utils


def init(mode=None, **kwargs):
    """Wrapper to create the XML API object you need to acces the CCU API.
    """
    try:
        return XMLAPI(**kwargs)
    except TypeError as e:
        raise PMException("You need to provide at least the address to access your CCU via XML-RPC (%s)." % e)


class XMLAPI(utils.LogMixin):
    """Implementation of the pmatic low level XML API.
    """
    def __init__(self, address, **kwargs):
        super(XMLAPI, self).__init__()
        self._methods = {}
        self._fail_exc = None
        self._initialized = False

        # For simplicity we only allow one thread to perform API calls at the time
        self._api_lock = threading.RLock()

        self._address = None

        self._set_address(address)


    # is called in locked context
    def _set_address(self, address):
        if not utils.is_string(address):
            raise PMException("Please specify the address of the CCU.")

        # Add optional protocol prefix
        if not address.startswith("https://") and not address.startswith("http://"):
            address = "http://%s:2001" % address
        else:
            address += ':2001'

        self._address = address


    # is called in unlocked context
    @property
    def initialized(self):
        """Tells the caller whether or not the "connection" with the CCU is ready
        for other API calls."""
        with self._api_lock:
            return self._initialized


    # is called in unlocked context
    @property
    def fail_reason(self):
        """When the API has not been initialized successfully, this provides access to the
        exception caused the problem. Otherwise it is set to *None*."""
        return self._fail_exc


    # is called in unlocked context
    @property
    def address(self):
        return self._address


    # is called in locked context
    def _initialize(self):
        if self.initialized:
            return

        self._fail_exc = None
        self.logger.debug("[XML-API] Initializing...")
        try:
            self._initialize_api()
            self._initialized = True
            self.logger.debug("[XML-API] Initialized")
        except Exception as e:
            self._initialized = False
            self._fail_exc = e
            raise


    # is called in locked context
    def _initialize_api(self):
        self._connect()
        self._init_methods()


    # is called in locked context
    def _to_internal_name(self, method_name_api):
        """Translates a raw API method name to the pmatic notation.

        These modifications are made:

        * . are replaced with _
        * BidCoS is replaced with bidcos
        * ReGa is replaced with rega
        * whole string is transformed from camel case to lowercase + underscore notation

        e.g. Interface.activateLinkParamset is changed to API.interface_activate_link_paramset
        """
        return utils.decamel(method_name_api.replace(".", "_")) \
                                            .replace("bid_co_s", "bidcos") \
                                            .replace("re_ga", "rega") \
                                            .replace("__", "_")


    # is called in unlocked context
    def print_methods(self):
        """Prints a description of the available API methods.

        This information has been fetched from the CCU before. This might be useful
        for working with the API to gather infos about the available calls.
        """
        with self._api_lock:
            self._initialize()

        line_format = "%-60s %s\n"
        sys.stdout.write(line_format % ("Method", "Description"))

        # TODO: Output device API methods
        for method_name_int, method in sorted(self._methods.items()):
            call_txt = "API.%s(%s)" % (method_name_int, ", ".join(method["INT_ARGUMENTS"]))
            sys.stdout.write(line_format % (call_txt, method["INFO"]))


    # is called in locked context
    def _connect(self):
        self.proxy = ServerProxy(self._address)


    # is called in locked context
    def _init_methods(self):
        """Parses the method configuration read from the CCU.

        The method configuration read with _get_methods_config() is being
        parsed here to initialize the self._methods dictionary which holds
        all need information about the available API methods.
        """
        self._methods.clear()

        methods = self.proxy.system.listMethods()

        for method in methods:
            method_name_int = self._to_internal_name(method)

            self._methods.setdefault(method_name_int,
                {
                    "NAME": method,
                    "INFO": "",
                    "ARGUMENTS": [],
                    "INT_ARGUMENTS": []
                }
             )


    # is called in locked context
    def _get_method(self, method_name_int):
        """Returns the method specification (dict) of the given API methods.

        The method name needs to be specified with it's internal name (like
        the methods of the API object are named). When the request API method
        does not exist a PMException is raised.
        """
        try:
            return self._methods[method_name_int]
        except KeyError:
            raise PMException("Method \"%s\" is not a valid method." % method_name_int)


    # is called from unlocked context
    def __getattr__(self, method_name_int):
        """Realizes dynamic methods based on the methods supported by the API.

        The method names are nearly the same as provided by the CCU
        (see http://[CCU_ADDRESS]/api/homematic.cgi or API.print_methods()).
        The method names are slighly renamed. For example CCU.getSerial() is
        available as API.ccu_get_serial() in pmatic. The translation is made
        by the _to_internal_name() method. For details take a look at that
        function.
        """
        with self._api_lock:
            self._initialize()

        return lambda *args: self._call(method_name_int, *args)


    # is called in unlocked context
    def _call(self, method_name_int, *args):
        """Runs the provided method, which needs to be one of the methods which are available
        on the device (with the given arguments) on the CCU."""
        with self._api_lock:
            return self._do_call(method_name_int, *args)


    # is called in locked context
    def _do_call(self, method_name_int, *args):
        method = self._get_method(method_name_int)
        methodToCall = getattr(self.proxy, method["NAME"])

        self.logger.debug("CALL: %s MODE: XML-RPC METHOD: %s ARGS: %r", self.address, method["NAME"], args)

        try:
            result = methodToCall(*args)
        except ProtocolError as perr:
            raise PMConnectionError("Unable to open \"%s\": %s" % (self.address,  perr))
        except Fault as fault:
            raise PMException("Server error calling \"%s\": %s" % (method_name_int, fault))

        self.logger.debug("  RESPONSE: %s", result)

        return result

