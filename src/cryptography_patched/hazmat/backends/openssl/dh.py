# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

from cryptography_patched import utils
from cryptography_patched.exceptions import UnsupportedAlgorithm, _Reasons
from cryptography_patched.hazmat.primitives import serialization
from cryptography_patched.hazmat.primitives.asymmetric import dh


def _dh_params_dup(dh_cdata, backend):
    lib = backend._lib
    ffi = backend._ffi

    param_cdata = lib.DHparams_dup(dh_cdata)
    backend.openssl_assert(param_cdata != ffi.NULL)
    param_cdata = ffi.gc(param_cdata, lib.DH_free)
    if lib.CRYPTOGRAPHY_OPENSSL_LESS_THAN_102:
        # In OpenSSL versions < 1.0.2 or libressl DHparams_dup don't copy q
        q = ffi.new("BIGNUM **")
        lib.DH_get0_pqg(dh_cdata, ffi.NULL, q, ffi.NULL)
        q_dup = lib.BN_dup(q[0])
        res = lib.DH_set0_pqg(param_cdata, ffi.NULL, q_dup, ffi.NULL)
        backend.openssl_assert(res == 1)

    return param_cdata


def _dh_cdata_to_parameters(dh_cdata, backend):
    param_cdata = _dh_params_dup(dh_cdata, backend)
    return _DHParameters(backend, param_cdata)


@utils.register_interface(dh.DHParametersWithSerialization)
class _DHParameters(object):
    def __init__(self, backend, dh_cdata):
        self._backend = backend
        self._dh_cdata = dh_cdata

    def parameter_numbers(self):
        p = self._backend._ffi.new("BIGNUM **")
        g = self._backend._ffi.new("BIGNUM **")
        q = self._backend._ffi.new("BIGNUM **")
        self._backend._lib.DH_get0_pqg(self._dh_cdata, p, q, g)
        self._backend.openssl_assert(p[0] != self._backend._ffi.NULL)
        self._backend.openssl_assert(g[0] != self._backend._ffi.NULL)
        if q[0] == self._backend._ffi.NULL:
            q_val = None
        else:
            q_val = self._backend._bn_to_int(q[0])
        return dh.DHParameterNumbers(
            p=self._backend._bn_to_int(p[0]),
            g=self._backend._bn_to_int(g[0]),
            q=q_val
        )

    def generate_private_key(self):
        return self._backend.generate_dh_private_key(self)

    def parameter_bytes(self, encoding, format):
        if format is not serialization.ParameterFormat.PKCS3:
            raise ValueError(
                "Only PKCS3 serialization is supported"
            )
        if not self._backend._lib.Cryptography_HAS_EVP_PKEY_DHX:
            q = self._backend._ffi.new("BIGNUM **")
            self._backend._lib.DH_get0_pqg(self._dh_cdata,
                                           self._backend._ffi.NULL,
                                           q,
                                           self._backend._ffi.NULL)
            if q[0] != self._backend._ffi.NULL:
                raise UnsupportedAlgorithm(
                    "DH X9.42 serialization is not supported",
                    _Reasons.UNSUPPORTED_SERIALIZATION)

        return self._backend._parameter_bytes(
            encoding,
            format,
            self._dh_cdata
        )


def _handle_dh_compute_key_error(errors, backend):
    lib = backend._lib

    backend.openssl_assert(
        errors[0]._lib_reason_match(
            lib.ERR_LIB_DH, lib.DH_R_INVALID_PUBKEY
        )
    )

    raise ValueError("Public key value is invalid for this exchange.")


def _get_dh_num_bits(backend, dh_cdata):
    p = backend._ffi.new("BIGNUM **")
    backend._lib.DH_get0_pqg(dh_cdata, p,
                             backend._ffi.NULL,
                             backend._ffi.NULL)
    backend.openssl_assert(p[0] != backend._ffi.NULL)
    return backend._lib.BN_num_bits(p[0])


@utils.register_interface(dh.DHPrivateKeyWithSerialization)
class _DHPrivateKey(object):
    def __init__(self, backend, dh_cdata, evp_pkey):
        self._backend = backend
        self._dh_cdata = dh_cdata
        self._evp_pkey = evp_pkey
        self._key_size_bytes = self._backend._lib.DH_size(dh_cdata)

    @property
    def key_size(self):
        return _get_dh_num_bits(self._backend, self._dh_cdata)

    def private_numbers(self):
        p = self._backend._ffi.new("BIGNUM **")
        g = self._backend._ffi.new("BIGNUM **")
        q = self._backend._ffi.new("BIGNUM **")
        self._backend._lib.DH_get0_pqg(self._dh_cdata, p, q, g)
        self._backend.openssl_assert(p[0] != self._backend._ffi.NULL)
        self._backend.openssl_assert(g[0] != self._backend._ffi.NULL)
        if q[0] == self._backend._ffi.NULL:
            q_val = None
        else:
            q_val = self._backend._bn_to_int(q[0])
        pub_key = self._backend._ffi.new("BIGNUM **")
        priv_key = self._backend._ffi.new("BIGNUM **")
        self._backend._lib.DH_get0_key(self._dh_cdata, pub_key, priv_key)
        self._backend.openssl_assert(pub_key[0] != self._backend._ffi.NULL)
        self._backend.openssl_assert(priv_key[0] != self._backend._ffi.NULL)
        return dh.DHPrivateNumbers(
            public_numbers=dh.DHPublicNumbers(
                parameter_numbers=dh.DHParameterNumbers(
                    p=self._backend._bn_to_int(p[0]),
                    g=self._backend._bn_to_int(g[0]),
                    q=q_val
                ),
                y=self._backend._bn_to_int(pub_key[0])
            ),
            x=self._backend._bn_to_int(priv_key[0])
        )

    def exchange(self, peer_public_key):

        buf = self._backend._ffi.new("unsigned char[]", self._key_size_bytes)
        pub_key = self._backend._ffi.new("BIGNUM **")
        self._backend._lib.DH_get0_key(peer_public_key._dh_cdata, pub_key,
                                       self._backend._ffi.NULL)
        self._backend.openssl_assert(pub_key[0] != self._backend._ffi.NULL)
        res = self._backend._lib.DH_compute_key(
            buf,
            pub_key[0],
            self._dh_cdata
        )

        if res == -1:
            errors = self._backend._consume_errors()
            return _handle_dh_compute_key_error(errors, self._backend)
        else:
            self._backend.openssl_assert(res >= 1)

            key = self._backend._ffi.buffer(buf)[:res]
            pad = self._key_size_bytes - len(key)

            if pad > 0:
                key = (b"\x00" * pad) + key

            return key

    def public_key(self):
        dh_cdata = _dh_params_dup(self._dh_cdata, self._backend)
        pub_key = self._backend._ffi.new("BIGNUM **")
        self._backend._lib.DH_get0_key(self._dh_cdata,
                                       pub_key, self._backend._ffi.NULL)
        self._backend.openssl_assert(pub_key[0] != self._backend._ffi.NULL)
        pub_key_dup = self._backend._lib.BN_dup(pub_key[0])
        self._backend.openssl_assert(pub_key_dup != self._backend._ffi.NULL)

        res = self._backend._lib.DH_set0_key(dh_cdata,
                                             pub_key_dup,
                                             self._backend._ffi.NULL)
        self._backend.openssl_assert(res == 1)
        evp_pkey = self._backend._dh_cdata_to_evp_pkey(dh_cdata)
        return _DHPublicKey(self._backend, dh_cdata, evp_pkey)

    def parameters(self):
        return _dh_cdata_to_parameters(self._dh_cdata, self._backend)

    def private_bytes(self, encoding, format, encryption_algorithm):
        if format is not serialization.PrivateFormat.PKCS8:
            raise ValueError(
                "DH private keys support only PKCS8 serialization"
            )
        if not self._backend._lib.Cryptography_HAS_EVP_PKEY_DHX:
            q = self._backend._ffi.new("BIGNUM **")
            self._backend._lib.DH_get0_pqg(self._dh_cdata,
                                           self._backend._ffi.NULL,
                                           q,
                                           self._backend._ffi.NULL)
            if q[0] != self._backend._ffi.NULL:
                raise UnsupportedAlgorithm(
                    "DH X9.42 serialization is not supported",
                    _Reasons.UNSUPPORTED_SERIALIZATION)

        return self._backend._private_key_bytes(
            encoding,
            format,
            encryption_algorithm,
            self._evp_pkey,
            self._dh_cdata
        )


@utils.register_interface(dh.DHPublicKeyWithSerialization)
class _DHPublicKey(object):
    def __init__(self, backend, dh_cdata, evp_pkey):
        self._backend = backend
        self._dh_cdata = dh_cdata
        self._evp_pkey = evp_pkey
        self._key_size_bits = _get_dh_num_bits(self._backend, self._dh_cdata)

    @property
    def key_size(self):
        return self._key_size_bits

    def public_numbers(self):
        p = self._backend._ffi.new("BIGNUM **")
        g = self._backend._ffi.new("BIGNUM **")
        q = self._backend._ffi.new("BIGNUM **")
        self._backend._lib.DH_get0_pqg(self._dh_cdata, p, q, g)
        self._backend.openssl_assert(p[0] != self._backend._ffi.NULL)
        self._backend.openssl_assert(g[0] != self._backend._ffi.NULL)
        if q[0] == self._backend._ffi.NULL:
            q_val = None
        else:
            q_val = self._backend._bn_to_int(q[0])
        pub_key = self._backend._ffi.new("BIGNUM **")
        self._backend._lib.DH_get0_key(self._dh_cdata,
                                       pub_key, self._backend._ffi.NULL)
        self._backend.openssl_assert(pub_key[0] != self._backend._ffi.NULL)
        return dh.DHPublicNumbers(
            parameter_numbers=dh.DHParameterNumbers(
                p=self._backend._bn_to_int(p[0]),
                g=self._backend._bn_to_int(g[0]),
                q=q_val
            ),
            y=self._backend._bn_to_int(pub_key[0])
        )

    def parameters(self):
        return _dh_cdata_to_parameters(self._dh_cdata, self._backend)

    def public_bytes(self, encoding, format):
        if format is not serialization.PublicFormat.SubjectPublicKeyInfo:
            raise ValueError(
                "DH public keys support only "
                "SubjectPublicKeyInfo serialization"
            )

        if not self._backend._lib.Cryptography_HAS_EVP_PKEY_DHX:
            q = self._backend._ffi.new("BIGNUM **")
            self._backend._lib.DH_get0_pqg(self._dh_cdata,
                                           self._backend._ffi.NULL,
                                           q,
                                           self._backend._ffi.NULL)
            if q[0] != self._backend._ffi.NULL:
                raise UnsupportedAlgorithm(
                    "DH X9.42 serialization is not supported",
                    _Reasons.UNSUPPORTED_SERIALIZATION)

        return self._backend._public_key_bytes(
            encoding,
            format,
            self,
            self._evp_pkey,
            None
        )
