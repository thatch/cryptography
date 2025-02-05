# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

import binascii

import pytest

from cryptography_patched.exceptions import (
    AlreadyFinalized, InvalidSignature, _Reasons
)
from cryptography_patched.hazmat.backends.interfaces import CMACBackend
from cryptography_patched.hazmat.primitives.ciphers.algorithms import (
    AES, ARC4, TripleDES
)
from cryptography_patched.hazmat.primitives.cmac import CMAC

from ...utils import (
    load_nist_vectors, load_vectors_from_file, raises_unsupported_algorithm
)


vectors_aes128 = load_vectors_from_file(
    "CMAC/nist-800-38b-aes128.txt", load_nist_vectors)

vectors_aes192 = load_vectors_from_file(
    "CMAC/nist-800-38b-aes192.txt", load_nist_vectors)

vectors_aes256 = load_vectors_from_file(
    "CMAC/nist-800-38b-aes256.txt", load_nist_vectors)

vectors_aes = vectors_aes128 + vectors_aes192 + vectors_aes256

vectors_3des = load_vectors_from_file(
    "CMAC/nist-800-38b-3des.txt", load_nist_vectors)

fake_key = b"\x00" * 16


@pytest.mark.requires_backend_interface(interface=CMACBackend)
class TestCMAC(object):
    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            AES(fake_key)),
        skip_message="Does not support CMAC."
    )
    @pytest.mark.parametrize("params", vectors_aes)
    def test_aes_generate(self, backend, params):
        key = params["key"]
        message = params["message"]
        output = params["output"]

        cmac = CMAC(AES(binascii.unhexlify(key)), backend)
        cmac.update(binascii.unhexlify(message))
        assert binascii.hexlify(cmac.finalize()) == output

    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            AES(fake_key)),
        skip_message="Does not support CMAC."
    )
    @pytest.mark.parametrize("params", vectors_aes)
    def test_aes_verify(self, backend, params):
        key = params["key"]
        message = params["message"]
        output = params["output"]

        cmac = CMAC(AES(binascii.unhexlify(key)), backend)
        cmac.update(binascii.unhexlify(message))
        assert cmac.verify(binascii.unhexlify(output)) is None

    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            TripleDES(fake_key)),
        skip_message="Does not support CMAC."
    )
    @pytest.mark.parametrize("params", vectors_3des)
    def test_3des_generate(self, backend, params):
        key1 = params["key1"]
        key2 = params["key2"]
        key3 = params["key3"]

        key = key1 + key2 + key3

        message = params["message"]
        output = params["output"]

        cmac = CMAC(TripleDES(binascii.unhexlify(key)), backend)
        cmac.update(binascii.unhexlify(message))
        assert binascii.hexlify(cmac.finalize()) == output

    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            TripleDES(fake_key)),
        skip_message="Does not support CMAC."
    )
    @pytest.mark.parametrize("params", vectors_3des)
    def test_3des_verify(self, backend, params):
        key1 = params["key1"]
        key2 = params["key2"]
        key3 = params["key3"]

        key = key1 + key2 + key3

        message = params["message"]
        output = params["output"]

        cmac = CMAC(TripleDES(binascii.unhexlify(key)), backend)
        cmac.update(binascii.unhexlify(message))
        assert cmac.verify(binascii.unhexlify(output)) is None

    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            AES(fake_key)),
        skip_message="Does not support CMAC."
    )
    def test_invalid_verify(self, backend):
        key = b"2b7e151628aed2a6abf7158809cf4f3c"
        cmac = CMAC(AES(key), backend)
        cmac.update(b"6bc1bee22e409f96e93d7e117393172a")

        with pytest.raises(InvalidSignature):
            cmac.verify(b"foobar")

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            ARC4(fake_key), None),
        skip_message="Does not support CMAC."
    )
    def test_invalid_algorithm(self, backend):
        key = b"0102030405"
        with pytest.raises(TypeError):
            CMAC(ARC4(key), backend)

    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            AES(fake_key)),
        skip_message="Does not support CMAC."
    )
    def test_raises_after_finalize(self, backend):
        key = b"2b7e151628aed2a6abf7158809cf4f3c"
        cmac = CMAC(AES(key), backend)
        cmac.finalize()

        with pytest.raises(AlreadyFinalized):
            cmac.update(b"foo")

        with pytest.raises(AlreadyFinalized):
            cmac.copy()

        with pytest.raises(AlreadyFinalized):
            cmac.finalize()

        with pytest.raises(AlreadyFinalized):
            cmac.verify(b"")

    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            AES(fake_key)),
        skip_message="Does not support CMAC."
    )
    def test_verify_reject_unicode(self, backend):
        key = b"2b7e151628aed2a6abf7158809cf4f3c"
        cmac = CMAC(AES(key), backend)

        with pytest.raises(TypeError):
            cmac.update(u'')

        with pytest.raises(TypeError):
            cmac.verify(u'')

    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            AES(fake_key)),
        skip_message="Does not support CMAC."
    )
    def test_copy_with_backend(self, backend):
        key = b"2b7e151628aed2a6abf7158809cf4f3c"
        cmac = CMAC(AES(key), backend)
        cmac.update(b"6bc1bee22e409f96e93d7e117393172a")
        copy_cmac = cmac.copy()
        assert cmac.finalize() == copy_cmac.finalize()

    @pytest.mark.supported(
        only_if=lambda backend: backend.cmac_algorithm_supported(
            AES(fake_key)),
        skip_message="Does not support CMAC."
    )
    def test_buffer_protocol(self, backend):
        key = bytearray(b"2b7e151628aed2a6abf7158809cf4f3c")
        cmac = CMAC(AES(key), backend)
        cmac.update(b"6bc1bee22e409f96e93d7e117393172a")
        assert cmac.finalize() == binascii.unhexlify(
            b"a21e6e647bfeaf5ca0a5e1bcd957dfad"
        )


def test_invalid_backend():
    key = b"2b7e151628aed2a6abf7158809cf4f3c"
    pretend_backend = object()

    with raises_unsupported_algorithm(_Reasons.BACKEND_MISSING_INTERFACE):
        CMAC(AES(key), pretend_backend)
