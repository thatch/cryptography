# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

import pytest

from cryptography_patched.hazmat.backends.interfaces import PBKDF2HMACBackend
from cryptography_patched.hazmat.primitives import hashes

from .utils import generate_pbkdf2_test
from ...utils import load_nist_vectors


@pytest.mark.supported(
    only_if=lambda backend: backend.pbkdf2_hmac_supported(hashes.SHA1()),
    skip_message="Does not support SHA1 for PBKDF2HMAC",
)
@pytest.mark.requires_backend_interface(interface=PBKDF2HMACBackend)
class TestPBKDF2HMACSHA1(object):
    test_pbkdf2_sha1 = generate_pbkdf2_test(
        load_nist_vectors,
        "KDF",
        [
            "rfc-6070-PBKDF2-SHA1.txt",
        ],
        hashes.SHA1(),
    )
