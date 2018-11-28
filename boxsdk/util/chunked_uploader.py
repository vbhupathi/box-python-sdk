from __future__ import unicode_literals, absolute_import

import hashlib


class ChunkedUploader(object):

    def __init__(self, upload_session, content_stream, file_size):
        self._upload_session = upload_session
        self._content_stream = content_stream
        self._file_size = file_size
        self._part_array = []
        self._sha1 = hashlib.sha1()
        self._inflight_part = None

    def start(self):
        self._upload()
        content_sha1 = self._sha1.digest()
        return self._upload_session.commit(content_sha1=content_sha1, parts=self._part_array)

    def _upload(self):
        while len(self._part_array) < self._upload_session.total_parts:
            next_part = self._inflight_part or self._get_next_part()
            self._inflight_part = next_part
            uploaded_part = self._inflight_part.upload()
            self._inflight_part = None
            self._part_array.append(uploaded_part)
            self._sha1.update(next_part.chunk)

    def _get_next_part(self):
        copied_length = 0
        chunk = b''
        offset = len(self._part_array) * self._upload_session.part_size
        while copied_length < self._upload_session.part_size:
            bytes_read = self._content_stream.read(self._upload_session.part_size - copied_length)
            if bytes_read is None:
                # stream returns none when no bytes are ready currently but there are
                # potentially more bytes in the stream to be read.
                continue
            if not bytes_read:
                # stream is exhausted.
                break
            chunk += bytes_read
            copied_length += len(bytes_read)
        return InflightPart(offset, chunk, self._upload_session, self._file_size)


class InflightPart(object):

    def __init__(self, offset, chunk, upload_session, total_size):
        self._offset = offset
        self._chunk = chunk
        self._upload_session = upload_session
        self._total_size = total_size

    @property
    def offset(self):
        return self._offset

    @property
    def chunk(self):
        return self._chunk

    def upload(self):
        return self._upload_session.upload_part_bytes(
            part_bytes=self.chunk,
            offset=self.offset,
            total_size=self._total_size)