# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

from __future__ import absolute_import, division, print_function

import struct

from cryptography_patched.hazmat.primitives.ciphers import Cipher
from cryptography_patched.hazmat.primitives.ciphers.algorithms import AES
from cryptography_patched.hazmat.primitives.ciphers.modes import ECB
from cryptography_patched.hazmat.primitives.constant_time import bytes_eq


def _wrap_core(wrapping_key, a, r, backend):
    # RFC 3394 Key Wrap - 2.2.1 (index method)
    encryptor = Cipher(AES(wrapping_key), ECB(), backend).encryptor()
    n = len(r)
    for j in range(6):
        for i in range(n):
            # every encryption operation is a discrete 16 byte chunk (because
            # AES has a 128-bit block size) and since we're using ECB it is
            # safe to reuse the encryptor for the entire operation
            b = encryptor.update(a + r[i])
            # pack/unpack are safe as these are always 64-bit chunks
            a = struct.pack(
                ">Q", struct.unpack(">Q", b[:8])[0] ^ ((n * j) + i + 1)
            )
            r[i] = b[-8:]

    assert encryptor.finalize() == b""

    return a + b"".join(r)


def aes_key_wrap(wrapping_key, key_to_wrap, backend):
    if len(wrapping_key) not in [16, 24, 32]:
        raise ValueError("The wrapping key must be a valid AES key length")

    if len(key_to_wrap) < 16:
        raise ValueError("The key to wrap must be at least 16 bytes")

    if len(key_to_wrap) % 8 != 0:
        raise ValueError("The key to wrap must be a multiple of 8 bytes")

    a = b"\xa6\xa6\xa6\xa6\xa6\xa6\xa6\xa6"
    r = [key_to_wrap[i:i + 8] for i in range(0, len(key_to_wrap), 8)]
    return _wrap_core(wrapping_key, a, r, backend)


def _unwrap_core(wrapping_key, a, r, backend):
    # Implement RFC 3394 Key Unwrap - 2.2.2 (index method)
    decryptor = Cipher(AES(wrapping_key), ECB(), backend).decryptor()
    n = len(r)
    for j in reversed(range(6)):
        for i in reversed(range(n)):
            # pack/unpack are safe as these are always 64-bit chunks
            atr = struct.pack(
                ">Q", struct.unpack(">Q", a)[0] ^ ((n * j) + i + 1)
            ) + r[i]
            # every decryption operation is a discrete 16 byte chunk so
            # it is safe to reuse the decryptor for the entire operation
            b = decryptor.update(atr)
            a = b[:8]
            r[i] = b[-8:]

    assert decryptor.finalize() == b""
    return a, r


def aes_key_wrap_with_padding(wrapping_key, key_to_wrap, backend):
    if len(wrapping_key) not in [16, 24, 32]:
        raise ValueError("The wrapping key must be a valid AES key length")

    aiv = b"\xA6\x59\x59\xA6" + struct.pack(">i", len(key_to_wrap))
    # pad the key to wrap if necessary
    pad = (8 - (len(key_to_wrap) % 8)) % 8
    key_to_wrap = key_to_wrap + b"\x00" * pad
    if len(key_to_wrap) == 8:
        # RFC 5649 - 4.1 - exactly 8 octets after padding
        encryptor = Cipher(AES(wrapping_key), ECB(), backend).encryptor()
        b = encryptor.update(aiv + key_to_wrap)
        assert encryptor.finalize() == b""
        return b
    else:
        r = [key_to_wrap[i:i + 8] for i in range(0, len(key_to_wrap), 8)]
        return _wrap_core(wrapping_key, aiv, r, backend)


def aes_key_unwrap_with_padding(wrapping_key, wrapped_key, backend):
    if len(wrapped_key) < 16:
        raise InvalidUnwrap("Must be at least 16 bytes")

    if len(wrapping_key) not in [16, 24, 32]:
        raise ValueError("The wrapping key must be a valid AES key length")

    if len(wrapped_key) == 16:
        # RFC 5649 - 4.2 - exactly two 64-bit blocks
        decryptor = Cipher(AES(wrapping_key), ECB(), backend).decryptor()
        b = decryptor.update(wrapped_key)
        assert decryptor.finalize() == b""
        a = b[:8]
        data = b[8:]
        n = 1
    else:
        r = [wrapped_key[i:i + 8] for i in range(0, len(wrapped_key), 8)]
        encrypted_aiv = r.pop(0)
        n = len(r)
        a, r = _unwrap_core(wrapping_key, encrypted_aiv, r, backend)
        data = b"".join(r)

    # 1) Check that MSB(32,A) = A65959A6.
    # 2) Check that 8*(n-1) < LSB(32,A) <= 8*n.  If so, let
    #    MLI = LSB(32,A).
    # 3) Let b = (8*n)-MLI, and then check that the rightmost b octets of
    #    the output data are zero.
    (mli,) = struct.unpack(">I", a[4:])
    b = (8 * n) - mli
    if (
        not bytes_eq(a[:4], b"\xa6\x59\x59\xa6") or not
        8 * (n - 1) < mli <= 8 * n or (
            b != 0 and not bytes_eq(data[-b:], b"\x00" * b)
        )
    ):
        raise InvalidUnwrap()

    if b == 0:
        return data
    else:
        return data[:-b]


def aes_key_unwrap(wrapping_key, wrapped_key, backend):
    if len(wrapped_key) < 24:
        raise InvalidUnwrap("Must be at least 24 bytes")

    if len(wrapped_key) % 8 != 0:
        raise InvalidUnwrap("The wrapped key must be a multiple of 8 bytes")

    if len(wrapping_key) not in [16, 24, 32]:
        raise ValueError("The wrapping key must be a valid AES key length")

    aiv = b"\xa6\xa6\xa6\xa6\xa6\xa6\xa6\xa6"
    r = [wrapped_key[i:i + 8] for i in range(0, len(wrapped_key), 8)]
    a = r.pop(0)
    a, r = _unwrap_core(wrapping_key, a, r, backend)
    if not bytes_eq(a, aiv):
        raise InvalidUnwrap()

    return b"".join(r)


class InvalidUnwrap(Exception):
    pass
