# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

import datetime
import operator

from cryptography_patched import utils, x509
from cryptography_patched.exceptions import UnsupportedAlgorithm
from cryptography_patched.hazmat.backends.openssl.decode_asn1 import (
    _CERTIFICATE_EXTENSION_PARSER, _CERTIFICATE_EXTENSION_PARSER_NO_SCT,
    _CRL_EXTENSION_PARSER, _CSR_EXTENSION_PARSER,
    _REVOKED_CERTIFICATE_EXTENSION_PARSER, _asn1_integer_to_int,
    _asn1_string_to_bytes, _decode_x509_name, _obj2txt, _parse_asn1_time
)
from cryptography_patched.hazmat.backends.openssl.encode_asn1 import (
    _encode_asn1_int_gc
)
from cryptography_patched.hazmat.primitives import hashes, serialization
from cryptography_patched.hazmat.primitives.asymmetric import dsa, ec, rsa


@utils.register_interface(x509.Certificate)
class _Certificate(object):
    def __init__(self, backend, x509):
        self._backend = backend
        self._x509 = x509

    def __repr__(self):
        return "<Certificate(subject={}, ...)>".format(self.subject)

    def __eq__(self, other):
        if not isinstance(other, x509.Certificate):
            return NotImplemented

        res = self._backend._lib.X509_cmp(self._x509, other._x509)
        return res == 0

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.public_bytes(serialization.Encoding.DER))

    def fingerprint(self, algorithm):
        h = hashes.Hash(algorithm, self._backend)
        h.update(self.public_bytes(serialization.Encoding.DER))
        return h.finalize()

    @property
    def version(self):
        version = self._backend._lib.X509_get_version(self._x509)
        if version == 0:
            return x509.Version.v1
        elif version == 2:
            return x509.Version.v3
        else:
            raise x509.InvalidVersion(
                "{} is not a valid X509 version".format(version), version
            )

    @property
    def serial_number(self):
        asn1_int = self._backend._lib.X509_get_serialNumber(self._x509)
        self._backend.openssl_assert(asn1_int != self._backend._ffi.NULL)
        return _asn1_integer_to_int(self._backend, asn1_int)

    def public_key(self):
        pkey = self._backend._lib.X509_get_pubkey(self._x509)
        if pkey == self._backend._ffi.NULL:
            # Remove errors from the stack.
            self._backend._consume_errors()
            raise ValueError("Certificate public key is of an unknown type")

        pkey = self._backend._ffi.gc(pkey, self._backend._lib.EVP_PKEY_free)

        return self._backend._evp_pkey_to_public_key(pkey)

    @property
    def not_valid_before(self):
        asn1_time = self._backend._lib.X509_getm_notBefore(self._x509)
        return _parse_asn1_time(self._backend, asn1_time)

    @property
    def not_valid_after(self):
        asn1_time = self._backend._lib.X509_getm_notAfter(self._x509)
        return _parse_asn1_time(self._backend, asn1_time)

    @property
    def issuer(self):
        issuer = self._backend._lib.X509_get_issuer_name(self._x509)
        self._backend.openssl_assert(issuer != self._backend._ffi.NULL)
        return _decode_x509_name(self._backend, issuer)

    @property
    def subject(self):
        subject = self._backend._lib.X509_get_subject_name(self._x509)
        self._backend.openssl_assert(subject != self._backend._ffi.NULL)
        return _decode_x509_name(self._backend, subject)

    @property
    def signature_hash_algorithm(self):
        oid = self.signature_algorithm_oid
        try:
            return x509._SIG_OIDS_TO_HASH[oid]
        except KeyError:
            raise UnsupportedAlgorithm(
                "Signature algorithm OID:{} not recognized".format(oid)
            )

    @property
    def signature_algorithm_oid(self):
        alg = self._backend._ffi.new("X509_ALGOR **")
        self._backend._lib.X509_get0_signature(
            self._backend._ffi.NULL, alg, self._x509
        )
        self._backend.openssl_assert(alg[0] != self._backend._ffi.NULL)
        oid = _obj2txt(self._backend, alg[0].algorithm)
        return x509.ObjectIdentifier(oid)

    @utils.cached_property
    def extensions(self):
        if self._backend._lib.CRYPTOGRAPHY_OPENSSL_110_OR_GREATER:
            return _CERTIFICATE_EXTENSION_PARSER.parse(
                self._backend, self._x509
            )
        else:
            return _CERTIFICATE_EXTENSION_PARSER_NO_SCT.parse(
                self._backend, self._x509
            )

    @property
    def signature(self):
        sig = self._backend._ffi.new("ASN1_BIT_STRING **")
        self._backend._lib.X509_get0_signature(
            sig, self._backend._ffi.NULL, self._x509
        )
        self._backend.openssl_assert(sig[0] != self._backend._ffi.NULL)
        return _asn1_string_to_bytes(self._backend, sig[0])

    @property
    def tbs_certificate_bytes(self):
        pp = self._backend._ffi.new("unsigned char **")
        res = self._backend._lib.i2d_re_X509_tbs(self._x509, pp)
        self._backend.openssl_assert(res > 0)
        pp = self._backend._ffi.gc(
            pp, lambda pointer: self._backend._lib.OPENSSL_free(pointer[0])
        )
        return self._backend._ffi.buffer(pp[0], res)[:]

    def public_bytes(self, encoding):
        bio = self._backend._create_mem_bio_gc()
        if encoding is serialization.Encoding.PEM:
            res = self._backend._lib.PEM_write_bio_X509(bio, self._x509)
        elif encoding is serialization.Encoding.DER:
            res = self._backend._lib.i2d_X509_bio(bio, self._x509)
        else:
            raise TypeError("encoding must be an item from the Encoding enum")

        self._backend.openssl_assert(res == 1)
        return self._backend._read_mem_bio(bio)


@utils.register_interface(x509.RevokedCertificate)
class _RevokedCertificate(object):
    def __init__(self, backend, crl, x509_revoked):
        self._backend = backend
        # The X509_REVOKED_value is a X509_REVOKED * that has
        # no reference counting. This means when X509_CRL_free is
        # called then the CRL and all X509_REVOKED * are freed. Since
        # you can retain a reference to a single revoked certificate
        # and let the CRL fall out of scope we need to retain a
        # private reference to the CRL inside the RevokedCertificate
        # object to prevent the gc from being called inappropriately.
        self._crl = crl
        self._x509_revoked = x509_revoked

    @property
    def serial_number(self):
        asn1_int = self._backend._lib.X509_REVOKED_get0_serialNumber(
            self._x509_revoked
        )
        self._backend.openssl_assert(asn1_int != self._backend._ffi.NULL)
        return _asn1_integer_to_int(self._backend, asn1_int)

    @property
    def revocation_date(self):
        return _parse_asn1_time(
            self._backend,
            self._backend._lib.X509_REVOKED_get0_revocationDate(
                self._x509_revoked
            )
        )

    @utils.cached_property
    def extensions(self):
        return _REVOKED_CERTIFICATE_EXTENSION_PARSER.parse(
            self._backend, self._x509_revoked
        )


@utils.register_interface(x509.CertificateRevocationList)
class _CertificateRevocationList(object):
    def __init__(self, backend, x509_crl):
        self._backend = backend
        self._x509_crl = x509_crl

    def __eq__(self, other):
        if not isinstance(other, x509.CertificateRevocationList):
            return NotImplemented

        res = self._backend._lib.X509_CRL_cmp(self._x509_crl, other._x509_crl)
        return res == 0

    def __ne__(self, other):
        return not self == other

    def fingerprint(self, algorithm):
        h = hashes.Hash(algorithm, self._backend)
        bio = self._backend._create_mem_bio_gc()
        res = self._backend._lib.i2d_X509_CRL_bio(
            bio, self._x509_crl
        )
        self._backend.openssl_assert(res == 1)
        der = self._backend._read_mem_bio(bio)
        h.update(der)
        return h.finalize()

    @utils.cached_property
    def _sorted_crl(self):
        # X509_CRL_get0_by_serial sorts in place, which breaks a variety of
        # things we don't want to break (like iteration and the signature).
        # Let's dupe it and sort that instead.
        dup = self._backend._lib.X509_CRL_dup(self._x509_crl)
        self._backend.openssl_assert(dup != self._backend._ffi.NULL)
        dup = self._backend._ffi.gc(dup, self._backend._lib.X509_CRL_free)
        return dup

    def get_revoked_certificate_by_serial_number(self, serial_number):
        revoked = self._backend._ffi.new("X509_REVOKED **")
        asn1_int = _encode_asn1_int_gc(self._backend, serial_number)
        res = self._backend._lib.X509_CRL_get0_by_serial(
            self._sorted_crl, revoked, asn1_int
        )
        if res == 0:
            return None
        else:
            self._backend.openssl_assert(
                revoked[0] != self._backend._ffi.NULL
            )
            return _RevokedCertificate(
                self._backend, self._sorted_crl, revoked[0]
            )

    @property
    def signature_hash_algorithm(self):
        oid = self.signature_algorithm_oid
        try:
            return x509._SIG_OIDS_TO_HASH[oid]
        except KeyError:
            raise UnsupportedAlgorithm(
                "Signature algorithm OID:{} not recognized".format(oid)
            )

    @property
    def signature_algorithm_oid(self):
        alg = self._backend._ffi.new("X509_ALGOR **")
        self._backend._lib.X509_CRL_get0_signature(
            self._x509_crl, self._backend._ffi.NULL, alg
        )
        self._backend.openssl_assert(alg[0] != self._backend._ffi.NULL)
        oid = _obj2txt(self._backend, alg[0].algorithm)
        return x509.ObjectIdentifier(oid)

    @property
    def issuer(self):
        issuer = self._backend._lib.X509_CRL_get_issuer(self._x509_crl)
        self._backend.openssl_assert(issuer != self._backend._ffi.NULL)
        return _decode_x509_name(self._backend, issuer)

    @property
    def next_update(self):
        nu = self._backend._lib.X509_CRL_get_nextUpdate(self._x509_crl)
        self._backend.openssl_assert(nu != self._backend._ffi.NULL)
        return _parse_asn1_time(self._backend, nu)

    @property
    def last_update(self):
        lu = self._backend._lib.X509_CRL_get_lastUpdate(self._x509_crl)
        self._backend.openssl_assert(lu != self._backend._ffi.NULL)
        return _parse_asn1_time(self._backend, lu)

    @property
    def signature(self):
        sig = self._backend._ffi.new("ASN1_BIT_STRING **")
        self._backend._lib.X509_CRL_get0_signature(
            self._x509_crl, sig, self._backend._ffi.NULL
        )
        self._backend.openssl_assert(sig[0] != self._backend._ffi.NULL)
        return _asn1_string_to_bytes(self._backend, sig[0])

    @property
    def tbs_certlist_bytes(self):
        pp = self._backend._ffi.new("unsigned char **")
        res = self._backend._lib.i2d_re_X509_CRL_tbs(self._x509_crl, pp)
        self._backend.openssl_assert(res > 0)
        pp = self._backend._ffi.gc(
            pp, lambda pointer: self._backend._lib.OPENSSL_free(pointer[0])
        )
        return self._backend._ffi.buffer(pp[0], res)[:]

    def public_bytes(self, encoding):
        bio = self._backend._create_mem_bio_gc()
        if encoding is serialization.Encoding.PEM:
            res = self._backend._lib.PEM_write_bio_X509_CRL(
                bio, self._x509_crl
            )
        elif encoding is serialization.Encoding.DER:
            res = self._backend._lib.i2d_X509_CRL_bio(bio, self._x509_crl)
        else:
            raise TypeError("encoding must be an item from the Encoding enum")

        self._backend.openssl_assert(res == 1)
        return self._backend._read_mem_bio(bio)

    def _revoked_cert(self, idx):
        revoked = self._backend._lib.X509_CRL_get_REVOKED(self._x509_crl)
        r = self._backend._lib.sk_X509_REVOKED_value(revoked, idx)
        self._backend.openssl_assert(r != self._backend._ffi.NULL)
        return _RevokedCertificate(self._backend, self, r)

    def __iter__(self):
        for i in range(len(self)):
            yield self._revoked_cert(i)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            start, stop, step = idx.indices(len(self))
            return [self._revoked_cert(i) for i in range(start, stop, step)]
        else:
            idx = operator.index(idx)
            if idx < 0:
                idx += len(self)
            if not 0 <= idx < len(self):
                raise IndexError
            return self._revoked_cert(idx)

    def __len__(self):
        revoked = self._backend._lib.X509_CRL_get_REVOKED(self._x509_crl)
        if revoked == self._backend._ffi.NULL:
            return 0
        else:
            return self._backend._lib.sk_X509_REVOKED_num(revoked)

    @utils.cached_property
    def extensions(self):
        return _CRL_EXTENSION_PARSER.parse(self._backend, self._x509_crl)

    def is_signature_valid(self, public_key):
        if not isinstance(public_key, (dsa.DSAPublicKey, rsa.RSAPublicKey,
                                       ec.EllipticCurvePublicKey)):
            raise TypeError('Expecting one of DSAPublicKey, RSAPublicKey,'
                            ' or EllipticCurvePublicKey.')
        res = self._backend._lib.X509_CRL_verify(
            self._x509_crl, public_key._evp_pkey
        )

        if res != 1:
            self._backend._consume_errors()
            return False

        return True


@utils.register_interface(x509.CertificateSigningRequest)
class _CertificateSigningRequest(object):
    def __init__(self, backend, x509_req):
        self._backend = backend
        self._x509_req = x509_req

    def __eq__(self, other):
        if not isinstance(other, _CertificateSigningRequest):
            return NotImplemented

        self_bytes = self.public_bytes(serialization.Encoding.DER)
        other_bytes = other.public_bytes(serialization.Encoding.DER)
        return self_bytes == other_bytes

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.public_bytes(serialization.Encoding.DER))

    def public_key(self):
        pkey = self._backend._lib.X509_REQ_get_pubkey(self._x509_req)
        self._backend.openssl_assert(pkey != self._backend._ffi.NULL)
        pkey = self._backend._ffi.gc(pkey, self._backend._lib.EVP_PKEY_free)
        return self._backend._evp_pkey_to_public_key(pkey)

    @property
    def subject(self):
        subject = self._backend._lib.X509_REQ_get_subject_name(self._x509_req)
        self._backend.openssl_assert(subject != self._backend._ffi.NULL)
        return _decode_x509_name(self._backend, subject)

    @property
    def signature_hash_algorithm(self):
        oid = self.signature_algorithm_oid
        try:
            return x509._SIG_OIDS_TO_HASH[oid]
        except KeyError:
            raise UnsupportedAlgorithm(
                "Signature algorithm OID:{} not recognized".format(oid)
            )

    @property
    def signature_algorithm_oid(self):
        alg = self._backend._ffi.new("X509_ALGOR **")
        self._backend._lib.X509_REQ_get0_signature(
            self._x509_req, self._backend._ffi.NULL, alg
        )
        self._backend.openssl_assert(alg[0] != self._backend._ffi.NULL)
        oid = _obj2txt(self._backend, alg[0].algorithm)
        return x509.ObjectIdentifier(oid)

    @utils.cached_property
    def extensions(self):
        x509_exts = self._backend._lib.X509_REQ_get_extensions(self._x509_req)
        x509_exts = self._backend._ffi.gc(
            x509_exts,
            lambda x: self._backend._lib.sk_X509_EXTENSION_pop_free(
                x, self._backend._ffi.addressof(
                    self._backend._lib._original_lib, "X509_EXTENSION_free"
                )
            )
        )
        return _CSR_EXTENSION_PARSER.parse(self._backend, x509_exts)

    def public_bytes(self, encoding):
        bio = self._backend._create_mem_bio_gc()
        if encoding is serialization.Encoding.PEM:
            res = self._backend._lib.PEM_write_bio_X509_REQ(
                bio, self._x509_req
            )
        elif encoding is serialization.Encoding.DER:
            res = self._backend._lib.i2d_X509_REQ_bio(bio, self._x509_req)
        else:
            raise TypeError("encoding must be an item from the Encoding enum")

        self._backend.openssl_assert(res == 1)
        return self._backend._read_mem_bio(bio)

    @property
    def tbs_certrequest_bytes(self):
        pp = self._backend._ffi.new("unsigned char **")
        res = self._backend._lib.i2d_re_X509_REQ_tbs(self._x509_req, pp)
        self._backend.openssl_assert(res > 0)
        pp = self._backend._ffi.gc(
            pp, lambda pointer: self._backend._lib.OPENSSL_free(pointer[0])
        )
        return self._backend._ffi.buffer(pp[0], res)[:]

    @property
    def signature(self):
        sig = self._backend._ffi.new("ASN1_BIT_STRING **")
        self._backend._lib.X509_REQ_get0_signature(
            self._x509_req, sig, self._backend._ffi.NULL
        )
        self._backend.openssl_assert(sig[0] != self._backend._ffi.NULL)
        return _asn1_string_to_bytes(self._backend, sig[0])

    @property
    def is_signature_valid(self):
        pkey = self._backend._lib.X509_REQ_get_pubkey(self._x509_req)
        self._backend.openssl_assert(pkey != self._backend._ffi.NULL)
        pkey = self._backend._ffi.gc(pkey, self._backend._lib.EVP_PKEY_free)
        res = self._backend._lib.X509_REQ_verify(self._x509_req, pkey)

        if res != 1:
            self._backend._consume_errors()
            return False

        return True


@utils.register_interface(
    x509.certificate_transparency.SignedCertificateTimestamp
)
class _SignedCertificateTimestamp(object):
    def __init__(self, backend, sct_list, sct):
        self._backend = backend
        # Keep the SCT_LIST that this SCT came from alive.
        self._sct_list = sct_list
        self._sct = sct

    @property
    def version(self):
        version = self._backend._lib.SCT_get_version(self._sct)
        assert version == self._backend._lib.SCT_VERSION_V1
        return x509.certificate_transparency.Version.v1

    @property
    def log_id(self):
        out = self._backend._ffi.new("unsigned char **")
        log_id_length = self._backend._lib.SCT_get0_log_id(self._sct, out)
        assert log_id_length >= 0
        return self._backend._ffi.buffer(out[0], log_id_length)[:]

    @property
    def timestamp(self):
        timestamp = self._backend._lib.SCT_get_timestamp(self._sct)
        milliseconds = timestamp % 1000
        return datetime.datetime.utcfromtimestamp(
            timestamp // 1000
        ).replace(microsecond=milliseconds * 1000)

    @property
    def entry_type(self):
        entry_type = self._backend._lib.SCT_get_log_entry_type(self._sct)
        # We currently only support loading SCTs from the X.509 extension, so
        # we only have precerts.
        assert entry_type == self._backend._lib.CT_LOG_ENTRY_TYPE_PRECERT
        return x509.certificate_transparency.LogEntryType.PRE_CERTIFICATE

    @property
    def _signature(self):
        ptrptr = self._backend._ffi.new("unsigned char **")
        res = self._backend._lib.SCT_get0_signature(self._sct, ptrptr)
        self._backend.openssl_assert(res > 0)
        self._backend.openssl_assert(ptrptr[0] != self._backend._ffi.NULL)
        return self._backend._ffi.buffer(ptrptr[0], res)[:]

    def __hash__(self):
        return hash(self._signature)

    def __eq__(self, other):
        if not isinstance(other, _SignedCertificateTimestamp):
            return NotImplemented

        return self._signature == other._signature

    def __ne__(self, other):
        return not self == other
