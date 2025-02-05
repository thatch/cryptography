# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

import pytest

from cryptography_patched.exceptions import (
    AlreadyFinalized, InvalidKey, _Reasons
)
from cryptography_patched.hazmat.backends import default_backend
from cryptography_patched.hazmat.primitives import hashes
from cryptography_patched.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ...doubles import DummyHashAlgorithm
from ...utils import raises_unsupported_algorithm


class TestPBKDF2HMAC(object):
    def test_already_finalized(self):
        kdf = PBKDF2HMAC(hashes.SHA1(), 20, b"salt", 10, default_backend())
        kdf.derive(b"password")
        with pytest.raises(AlreadyFinalized):
            kdf.derive(b"password2")

        kdf = PBKDF2HMAC(hashes.SHA1(), 20, b"salt", 10, default_backend())
        key = kdf.derive(b"password")
        with pytest.raises(AlreadyFinalized):
            kdf.verify(b"password", key)

        kdf = PBKDF2HMAC(hashes.SHA1(), 20, b"salt", 10, default_backend())
        kdf.verify(b"password", key)
        with pytest.raises(AlreadyFinalized):
            kdf.verify(b"password", key)

    def test_unsupported_algorithm(self):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            PBKDF2HMAC(
                DummyHashAlgorithm(), 20, b"salt", 10, default_backend()
            )

    def test_invalid_key(self):
        kdf = PBKDF2HMAC(hashes.SHA1(), 20, b"salt", 10, default_backend())
        key = kdf.derive(b"password")

        kdf = PBKDF2HMAC(hashes.SHA1(), 20, b"salt", 10, default_backend())
        with pytest.raises(InvalidKey):
            kdf.verify(b"password2", key)

    def test_unicode_error_with_salt(self):
        with pytest.raises(TypeError):
            PBKDF2HMAC(hashes.SHA1(), 20, u"salt", 10, default_backend())

    def test_unicode_error_with_key_material(self):
        kdf = PBKDF2HMAC(hashes.SHA1(), 20, b"salt", 10, default_backend())
        with pytest.raises(TypeError):
            kdf.derive(u"unicode here")

    def test_buffer_protocol(self, backend):
        kdf = PBKDF2HMAC(hashes.SHA1(), 10, b"salt", 10, default_backend())
        data = bytearray(b"data")
        assert kdf.derive(data) == b"\xe9n\xaa\x81\xbbt\xa4\xf6\x08\xce"


def test_invalid_backend():
    pretend_backend = object()

    with raises_unsupported_algorithm(_Reasons.BACKEND_MISSING_INTERFACE):
        PBKDF2HMAC(hashes.SHA1(), 20, b"salt", 10, pretend_backend)
