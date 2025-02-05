# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

import warnings

from cryptography_patched import utils
from cryptography_patched.hazmat.primitives import hashes
from cryptography_patched.hazmat.primitives.asymmetric.utils import Prehashed


def _evp_pkey_derive(backend, evp_pkey, peer_public_key):
    ctx = backend._lib.EVP_PKEY_CTX_new(evp_pkey, backend._ffi.NULL)
    backend.openssl_assert(ctx != backend._ffi.NULL)
    ctx = backend._ffi.gc(ctx, backend._lib.EVP_PKEY_CTX_free)
    res = backend._lib.EVP_PKEY_derive_init(ctx)
    backend.openssl_assert(res == 1)
    res = backend._lib.EVP_PKEY_derive_set_peer(
        ctx, peer_public_key._evp_pkey
    )
    backend.openssl_assert(res == 1)
    keylen = backend._ffi.new("size_t *")
    res = backend._lib.EVP_PKEY_derive(ctx, backend._ffi.NULL, keylen)
    backend.openssl_assert(res == 1)
    backend.openssl_assert(keylen[0] > 0)
    buf = backend._ffi.new("unsigned char[]", keylen[0])
    res = backend._lib.EVP_PKEY_derive(ctx, buf, keylen)
    if res != 1:
        raise ValueError(
            "Null shared key derived from public/private pair."
        )

    return backend._ffi.buffer(buf, keylen[0])[:]


def _calculate_digest_and_algorithm(backend, data, algorithm):
    if not isinstance(algorithm, Prehashed):
        hash_ctx = hashes.Hash(algorithm, backend)
        hash_ctx.update(data)
        data = hash_ctx.finalize()
    else:
        algorithm = algorithm._algorithm

    if len(data) != algorithm.digest_size:
        raise ValueError(
            "The provided data must be the same length as the hash "
            "algorithm's digest size."
        )

    return (data, algorithm)


def _check_not_prehashed(signature_algorithm):
    if isinstance(signature_algorithm, Prehashed):
        raise TypeError(
            "Prehashed is only supported in the sign and verify methods. "
            "It cannot be used with signer or verifier."
        )


def _warn_sign_verify_deprecated():
    warnings.warn(
        "signer and verifier have been deprecated. Please use sign "
        "and verify instead.",
        utils.PersistentlyDeprecated2017,
        stacklevel=3
    )
