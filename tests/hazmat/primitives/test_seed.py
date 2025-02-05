# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

import binascii
import os

import pytest

from cryptography_patched.hazmat.backends.interfaces import CipherBackend
from cryptography_patched.hazmat.primitives.ciphers import algorithms, modes

from .utils import generate_encrypt_test
from ...utils import load_nist_vectors


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.SEED(b"\x00" * 16), modes.ECB()
    ),
    skip_message="Does not support SEED ECB",
)
@pytest.mark.requires_backend_interface(interface=CipherBackend)
class TestSEEDModeECB(object):
    test_ecb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "SEED"),
        ["rfc-4269.txt"],
        lambda key, **kwargs: algorithms.SEED(binascii.unhexlify((key))),
        lambda **kwargs: modes.ECB(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.SEED(b"\x00" * 16), modes.CBC(b"\x00" * 16)
    ),
    skip_message="Does not support SEED CBC",
)
@pytest.mark.requires_backend_interface(interface=CipherBackend)
class TestSEEDModeCBC(object):
    test_cbc = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "SEED"),
        ["rfc-4196.txt"],
        lambda key, **kwargs: algorithms.SEED(binascii.unhexlify((key))),
        lambda iv, **kwargs: modes.CBC(binascii.unhexlify(iv))
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.SEED(b"\x00" * 16), modes.OFB(b"\x00" * 16)
    ),
    skip_message="Does not support SEED OFB",
)
@pytest.mark.requires_backend_interface(interface=CipherBackend)
class TestSEEDModeOFB(object):
    test_ofb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "SEED"),
        ["seed-ofb.txt"],
        lambda key, **kwargs: algorithms.SEED(binascii.unhexlify((key))),
        lambda iv, **kwargs: modes.OFB(binascii.unhexlify(iv))
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.SEED(b"\x00" * 16), modes.CFB(b"\x00" * 16)
    ),
    skip_message="Does not support SEED CFB",
)
@pytest.mark.requires_backend_interface(interface=CipherBackend)
class TestSEEDModeCFB(object):
    test_cfb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "SEED"),
        ["seed-cfb.txt"],
        lambda key, **kwargs: algorithms.SEED(binascii.unhexlify((key))),
        lambda iv, **kwargs: modes.CFB(binascii.unhexlify(iv))
    )
