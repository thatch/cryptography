# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

from cryptography_patched import exceptions, utils
from cryptography_patched.hazmat.primitives import serialization
from cryptography_patched.hazmat.primitives.asymmetric.ed448 import (
    Ed448PrivateKey, Ed448PublicKey
)

_ED448_KEY_SIZE = 57
_ED448_SIG_SIZE = 114


@utils.register_interface(Ed448PublicKey)
class _Ed448PublicKey(object):
    def __init__(self, backend, evp_pkey):
        self._backend = backend
        self._evp_pkey = evp_pkey

    def public_bytes(self, encoding, format):
        if (
            encoding is serialization.Encoding.Raw or
            format is serialization.PublicFormat.Raw
        ):
            if (
                encoding is not serialization.Encoding.Raw or
                format is not serialization.PublicFormat.Raw
            ):
                raise ValueError(
                    "When using Raw both encoding and format must be Raw"
                )

            return self._raw_public_bytes()

        if (
            encoding in serialization._PEM_DER and
            format is not serialization.PublicFormat.SubjectPublicKeyInfo
        ):
            raise ValueError(
                "format must be SubjectPublicKeyInfo when encoding is PEM or "
                "DER"
            )

        return self._backend._public_key_bytes(
            encoding, format, self, self._evp_pkey, None
        )

    def _raw_public_bytes(self):
        buf = self._backend._ffi.new("unsigned char []", _ED448_KEY_SIZE)
        buflen = self._backend._ffi.new("size_t *", _ED448_KEY_SIZE)
        res = self._backend._lib.EVP_PKEY_get_raw_public_key(
            self._evp_pkey, buf, buflen
        )
        self._backend.openssl_assert(res == 1)
        self._backend.openssl_assert(buflen[0] == _ED448_KEY_SIZE)
        return self._backend._ffi.buffer(buf, _ED448_KEY_SIZE)[:]

    def verify(self, signature, data):
        evp_md_ctx = self._backend._lib.Cryptography_EVP_MD_CTX_new()
        self._backend.openssl_assert(evp_md_ctx != self._backend._ffi.NULL)
        evp_md_ctx = self._backend._ffi.gc(
            evp_md_ctx, self._backend._lib.Cryptography_EVP_MD_CTX_free
        )
        res = self._backend._lib.EVP_DigestVerifyInit(
            evp_md_ctx, self._backend._ffi.NULL, self._backend._ffi.NULL,
            self._backend._ffi.NULL, self._evp_pkey
        )
        self._backend.openssl_assert(res == 1)
        res = self._backend._lib.EVP_DigestVerify(
            evp_md_ctx, signature, len(signature), data, len(data)
        )
        if res != 1:
            self._backend._consume_errors()
            raise exceptions.InvalidSignature


@utils.register_interface(Ed448PrivateKey)
class _Ed448PrivateKey(object):
    def __init__(self, backend, evp_pkey):
        self._backend = backend
        self._evp_pkey = evp_pkey

    def public_key(self):
        buf = self._backend._ffi.new("unsigned char []", _ED448_KEY_SIZE)
        buflen = self._backend._ffi.new("size_t *", _ED448_KEY_SIZE)
        res = self._backend._lib.EVP_PKEY_get_raw_public_key(
            self._evp_pkey, buf, buflen
        )
        self._backend.openssl_assert(res == 1)
        self._backend.openssl_assert(buflen[0] == _ED448_KEY_SIZE)
        public_bytes = self._backend._ffi.buffer(buf)[:]
        return self._backend.ed448_load_public_bytes(public_bytes)

    def sign(self, data):
        evp_md_ctx = self._backend._lib.Cryptography_EVP_MD_CTX_new()
        self._backend.openssl_assert(evp_md_ctx != self._backend._ffi.NULL)
        evp_md_ctx = self._backend._ffi.gc(
            evp_md_ctx, self._backend._lib.Cryptography_EVP_MD_CTX_free
        )
        res = self._backend._lib.EVP_DigestSignInit(
            evp_md_ctx, self._backend._ffi.NULL, self._backend._ffi.NULL,
            self._backend._ffi.NULL, self._evp_pkey
        )
        self._backend.openssl_assert(res == 1)
        buf = self._backend._ffi.new("unsigned char[]", _ED448_SIG_SIZE)
        buflen = self._backend._ffi.new("size_t *", len(buf))
        res = self._backend._lib.EVP_DigestSign(
            evp_md_ctx, buf, buflen, data, len(data)
        )
        self._backend.openssl_assert(res == 1)
        self._backend.openssl_assert(buflen[0] == _ED448_SIG_SIZE)
        return self._backend._ffi.buffer(buf, buflen[0])[:]

    def private_bytes(self, encoding, format, encryption_algorithm):
        if (
            encoding is serialization.Encoding.Raw or
            format is serialization.PublicFormat.Raw
        ):
            if (
                format is not serialization.PrivateFormat.Raw or
                encoding is not serialization.Encoding.Raw or not
                isinstance(encryption_algorithm, serialization.NoEncryption)
            ):
                raise ValueError(
                    "When using Raw both encoding and format must be Raw "
                    "and encryption_algorithm must be NoEncryption()"
                )

            return self._raw_private_bytes()

        if (
            encoding in serialization._PEM_DER and
            format is not serialization.PrivateFormat.PKCS8
        ):
            raise ValueError(
                "format must be PKCS8 when encoding is PEM or DER"
            )

        return self._backend._private_key_bytes(
            encoding, format, encryption_algorithm, self._evp_pkey, None
        )

    def _raw_private_bytes(self):
        buf = self._backend._ffi.new("unsigned char []", _ED448_KEY_SIZE)
        buflen = self._backend._ffi.new("size_t *", _ED448_KEY_SIZE)
        res = self._backend._lib.EVP_PKEY_get_raw_private_key(
            self._evp_pkey, buf, buflen
        )
        self._backend.openssl_assert(res == 1)
        self._backend.openssl_assert(buflen[0] == _ED448_KEY_SIZE)
        return self._backend._ffi.buffer(buf, _ED448_KEY_SIZE)[:]
