# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import datetime
import logging
import os
import sys
import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptoauthlib import *

logger = logging.getLogger(__name__)


def _split_equal_parts(line, n):
    return [line[i:i+n] for i in range(0, len(line), n)]


def _ascii_hex_string(a, l=16):
    """
    Format a bytearray object into a formatted ascii hex string
    """
    return '\n'.join(x.hex().upper() for x in _split_equal_parts(a, l))


def _convert_ec_pub_to_pem(raw_pub_key):
    """
    Convert to the key to PEM format. Expects bytes
    """
    public_key_der = bytearray.fromhex(
        '3059301306072A8648CE3D020106082A8648CE3D03010703420004') + raw_pub_key
    public_key_b64 = base64.b64encode(public_key_der).decode('ascii')
    public_key_pem = '-----BEGIN PUBLIC KEY-----\n%s\n-----END PUBLIC KEY-----' % '\n'.join(
        _split_equal_parts(public_key_b64, 64))
    return public_key_pem


def _ecc608_check_address(bus, address):
    cfg = cfg_ateccx08a_i2c_default()
    # Cryptolib uses 8-bit address.
    cfg.cfg.atcai2c.slave_address = address << 1
    cfg.cfg.atcai2c.bus = bus  # ARM I2C
    cfg.devtype = 3  # ECC608
    status = atcab_init(cfg)
    if status == 0:
        return True
    return False


def ecc608_find_chip():
    """Returns the I2C address of the crypto chip or None if chip is not installed."""

    # Bus and address can change for Pi/Dev Board as well as if using enviro.
    for bus in (0, 1):
        for addr in (0x30, 0x60, 0x62):
            if _ecc608_check_address(bus, addr):
                logger.info('Found crypto chip at 0x%x', addr)
                return addr
    logger.warning('No crypto detected, using SW.')
    return None


def ecc608_hw_sign(msg, key_id=0):
    digest = bytearray(32)
    status = atcab_sha(len(msg), msg, digest)
    assert status == 0

    signature = bytearray(64)
    status = atcab_sign(key_id, digest, signature)
    assert status == 0
    return signature


def ecc608_man_jwt(claims):
    header = '{"typ":"JWT","alg":"ES256"}'

    for k, v in claims.items():
        if type(v) is datetime.datetime:
            claims[k] = int(v.timestamp())

    payload = json.dumps(claims)

    token = base64.urlsafe_b64encode(
        header.encode('ascii')).replace(b'=', b'') + b'.'

    token = token + \
        base64.urlsafe_b64encode(payload.encode('ascii')).replace(b'=', b'')

    signature = ecc608_hw_sign(token)

    token = token + b'.' + \
        base64.urlsafe_b64encode(signature).replace(b'=', b'')
    return token


def ecc608_serial():
    serial = bytearray(9)
    assert atcab_read_serial_number(serial) == 0
    return _ascii_hex_string(serial)


def ecc608_public_key(key_id=0):
    public_key = bytearray(64)
    status = atcab_get_pubkey(key_id, public_key)
    assert status == 0
    return _convert_ec_pub_to_pem(public_key)


class HwEcAlgorithm(jwt.algorithms.Algorithm):
    def __init__(self):
        self.hash_alg = hashes.SHA256

    def prepare_key(self, key):
        return key

    def sign(self, msg, key):
        return ecc608_hw_sign(msg)

    def verify(self, msg, key, sig):
        try:
            der_sig = jwt.utils.raw_to_der_signature(sig, key.curve)
        except ValueError:
            return False

        try:
            key.verify(der_sig, msg, ec.ECDSA(self.hash_alg()))
            return True
        except InvalidSignature:
            return False


# On module import, load library.
try:
    ecc608_i2c_address = None
    ecc608_jwt_with_hw_alg = None

    load_cryptoauthlib()

    ecc608_i2c_address = ecc608_find_chip()
    if ecc608_i2c_address is not None:
        ecc608_jwt_with_hw_alg = jwt.PyJWT(algorithms=[])
        ecc608_jwt_with_hw_alg.register_algorithm('ES256', HwEcAlgorithm())
except Exception:
    logger.warning('Unable to load HW crypto library, using SW.')
