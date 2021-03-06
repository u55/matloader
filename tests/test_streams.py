""" Testing

"""

from __future__ import division, print_function, absolute_import

import os
import sys
import zlib

from io import BytesIO

if sys.version_info[0] >= 3:
    cStringIO = BytesIO
else:
    from cStringIO import StringIO as cStringIO

from tempfile import TemporaryFile

import numpy as np

from nose.tools import (
    assert_true, assert_false, assert_equal, assert_raises, with_setup)

from numpy.testing import (assert_array_equal, assert_array_almost_equal,
                           run_module_suite)

from matloader.streams import (
    GenericStream, cStringStream, FileStream, ZlibInputStream, make_stream,
    _readinto, _read_string)


streams = None


def setup_test():
    global streams
    val = b'a\x00string'
    fs = TemporaryFile()
    fs.write(val)
    fs.seek(0)
    gs = BytesIO(val)
    cs = cStringIO(val)
    streams = [fs, gs, cs]


def teardown_test():
    for st in streams:
        st.close()


@with_setup(setup_test, teardown_test)
def test_make_stream():
    # test stream initialization
    fs, gs, cs = streams
    assert_true(isinstance(make_stream(gs), GenericStream))
    if sys.version_info[0] < 3:
        assert_true(isinstance(make_stream(cs), cStringStream))
        assert_true(isinstance(make_stream(fs), FileStream))


@with_setup(setup_test, teardown_test)
def test_tell_seek():
    for s in streams:
        st = make_stream(s)
        res = st.seek(0)
        yield assert_equal, res, 0
        yield assert_equal, st.tell(), 0
        res = st.seek(5)
        yield assert_equal, res, 0
        yield assert_equal, st.tell(), 5
        res = st.seek(2, 1)
        yield assert_equal, res, 0
        yield assert_equal, st.tell(), 7
        res = st.seek(-2, 2)
        yield assert_equal, res, 0
        yield assert_equal, st.tell(), 6


def test_read():
    for s in streams:
        st = make_stream(s)
        st.seek(0)
        res = st.read(-1)
        yield assert_equal, res, b'a\x00string'
        st.seek(0)
        res = st.read(4)
        yield assert_equal, res, b'a\x00st'
        # read into
        st.seek(0)
        res = _readinto(st, 4)
        yield assert_equal, res, b'a\x00st'
        res = _readinto(st, 4)
        yield assert_equal, res, b'ring'
        yield assert_raises, IOError, _readinto, st, 2
        # read alloc
        st.seek(0)
        res = _read_string(st, 4)
        yield assert_equal, res, b'a\x00st'
        res = _read_string(st, 4)
        yield assert_equal, res, b'ring'
        yield assert_raises, IOError, _read_string, st, 2


class TestZlibInputStream(object):
    def _get_data(self, size):
        data = np.random.randint(0, 256, size).astype(np.uint8).tostring()
        compressed_data = zlib.compress(data)
        stream = BytesIO(compressed_data)
        return stream, len(compressed_data), data

    def test_read(self):
        block_size = 131072

        SIZES = [0, 1, 10, block_size//2, block_size-1,
                 block_size, block_size+1, 2*block_size-1]

        READ_SIZES = [block_size//2, block_size-1,
                      block_size, block_size+1]

        def check(size, read_size):
            compressed_stream, compressed_data_len, data = self._get_data(size)
            stream = ZlibInputStream(compressed_stream, compressed_data_len)
            data2 = b''
            so_far = 0
            while True:
                block = stream.read(min(read_size,
                                        size - so_far))
                if not block:
                    break
                so_far += len(block)
                data2 += block
            assert_equal(data, data2)

        for size in SIZES:
            for read_size in READ_SIZES:
                yield check, size, read_size

    def test_read_max_length(self):
        size = 1234
        data = np.random.randint(0, 256, size).astype(np.uint8).tostring()
        compressed_data = zlib.compress(data)
        compressed_stream = BytesIO(compressed_data + b"abbacaca")
        stream = ZlibInputStream(compressed_stream, len(compressed_data))

        stream.read(len(data))
        assert_equal(compressed_stream.tell(), len(compressed_data))

        assert_equal(stream.read(1), b"")

    def test_seek(self):
        compressed_stream, compressed_data_len, data = self._get_data(1024)

        stream = ZlibInputStream(compressed_stream, compressed_data_len)

        stream.seek(123)
        p = 123
        assert_equal(stream.tell(), p)
        d1 = stream.read(11)
        assert_equal(d1, data[p:p+11])

        stream.seek(321, 1)
        p = 123+11+321
        assert_equal(stream.tell(), p)
        d2 = stream.read(21)
        assert_equal(d2, data[p:p+21])

        stream.seek(641, 0)
        p = 641
        assert_equal(stream.tell(), p)
        d3 = stream.read(11)
        assert_equal(d3, data[p:p+11])

        assert_raises(IOError, stream.seek, 10, 2)
        assert_raises(IOError, stream.seek, -1, 1)
        assert_raises(ValueError, stream.seek, 1, 123)

        stream.seek(10000, 1)
        assert_equal(stream.read(12), b"")

    def test_all_data_read(self):
        compressed_stream, compressed_data_len, data = self._get_data(1024)
        stream = ZlibInputStream(compressed_stream, compressed_data_len)
        assert_false(stream.all_data_read())
        stream.seek(512)
        assert_false(stream.all_data_read())
        stream.seek(1024)
        assert_true(stream.all_data_read())


if __name__ == "__main__":
    run_module_suite()
