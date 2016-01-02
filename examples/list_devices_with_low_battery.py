#!/usr/bin/env python
# encoding: utf-8
#
# pmatic - A simple API to to the Homematic CCU2
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

# http://www.eq-3.de/Downloads/PDFs/Dokumentation_und_Tutorials/HM_XmlRpc_V1_502__2_.pdf
# http://www.eq-3.de/Downloads/Software/HM-CCU2-Firmware_Updates/Tutorials/hm_devices_Endkunden.pdf
# https://sites.google.com/site/homematicplayground/api/json-rpc

# Add Python 3.x behaviour to 2.7
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pmatic.api
from pmatic.entities import Device

API = pmatic.api.init(
    address="http://192.168.1.26",
    credentials=("Admin", "EPIC-SECRET-PW"),
    connect_timeout=5,
)

print("Low battery: ")
for device in Device.get_devices(API):
    if device.battery_low():
        print("  %s" % device.name)
else:
    print("  All battery powered devices are fine.")
