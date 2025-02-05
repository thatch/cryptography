# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function


from cryptography_patched import utils
from cryptography_patched.exceptions import (
    InvalidSignature, UnsupportedAlgorithm, _Reasons
)
from cryptography_patched.hazmat.primitives import constant_time, hashes


@utils.register_interface(hashes.HashContext)
class _HMACContext(object):
    def __init__(self, backend, key, algorithm, ctx=None):
        self._algorithm = algorithm
        self._backend = backend

        if ctx is None:
            ctx = self._backend._lib.Cryptography_HMAC_CTX_new()
            self._backend.openssl_assert(ctx != self._backend._ffi.NULL)
            ctx = self._backend._ffi.gc(
                ctx, self._backend._lib.Cryptography_HMAC_CTX_free
            )
            evp_md = self._backend._evp_md_from_algorithm(algorithm)
            if evp_md == self._backend._ffi.NULL:
                raise UnsupportedAlgorithm(
                    "{} is not a supported hash on this backend".format(
                        algorithm.name),
                    _Reasons.UNSUPPORTED_HASH
                )
            key_ptr = self._backend._ffi.from_buffer(key)
            res = self._backend._lib.HMAC_Init_ex(
                ctx, key_ptr, len(key), evp_md, self._backend._ffi.NULL
            )
            self._backend.openssl_assert(res != 0)

        self._ctx = ctx
        self._key = key

    algorithm = utils.read_only_property("_algorithm")

    def copy(self):
        copied_ctx = self._backend._lib.Cryptography_HMAC_CTX_new()
        self._backend.openssl_assert(copied_ctx != self._backend._ffi.NULL)
        copied_ctx = self._backend._ffi.gc(
            copied_ctx, self._backend._lib.Cryptography_HMAC_CTX_free
        )
        res = self._backend._lib.HMAC_CTX_copy(copied_ctx, self._ctx)
        self._backend.openssl_assert(res != 0)
        return _HMACContext(
            self._backend, self._key, self.algorithm, ctx=copied_ctx
        )

    def update(self, data):
        data_ptr = self._backend._ffi.from_buffer(data)
        res = self._backend._lib.HMAC_Update(self._ctx, data_ptr, len(data))
        self._backend.openssl_assert(res != 0)

    def finalize(self):
        buf = self._backend._ffi.new("unsigned char[]",
                                     self._backend._lib.EVP_MAX_MD_SIZE)
        outlen = self._backend._ffi.new("unsigned int *")
        res = self._backend._lib.HMAC_Final(self._ctx, buf, outlen)
        self._backend.openssl_assert(res != 0)
        self._backend.openssl_assert(outlen[0] == self.algorithm.digest_size)
        return self._backend._ffi.buffer(buf)[:outlen[0]]

    def verify(self, signature):
        digest = self.finalize()
        if not constant_time.bytes_eq(digest, signature):
            raise InvalidSignature("Signature did not match digest.")
