"""Base128 Encoding and Decoding Engine for Search3000 On-Disk Storage.

Encodes raw bytes, text, and JSON structures into 7-bit Base128 representations,
persisting indexed web pages and inverted index postings into the disk folder:
`data/indexed_sites_base128/`
"""

import json
import zlib
from typing import Any, Union


class Base128Codec:
    """Provides 7-bit Base128 bit-packing and unpacking with optional compression."""

    @staticmethod
    def encode_bytes(data: bytes) -> bytes:
        """Packs an 8-bit byte array into a 7-bit Base128 byte stream."""
        if not data:
            return b""
        
        # We process bits: 8-bit stream -> 7-bit stream
        bit_buffer = 0
        bit_count = 0
        output = bytearray()

        for b in data:
            bit_buffer = (bit_buffer << 8) | b
            bit_count += 8
            while bit_count >= 7:
                bit_count -= 7
                val = (bit_buffer >> bit_count) & 0x7F
                output.append(val)

        if bit_count > 0:
            val = (bit_buffer << (7 - bit_count)) & 0x7F
            output.append(val)

        return bytes(output)

    @staticmethod
    def decode_bytes(b128_data: bytes, original_len: int = -1) -> bytes:
        """Unpacks a 7-bit Base128 byte stream back into the original 8-bit byte array."""
        if not b128_data:
            return b""

        bit_buffer = 0
        bit_count = 0
        output = bytearray()

        for val in b128_data:
            bit_buffer = (bit_buffer << 7) | (val & 0x7F)
            bit_count += 7
            while bit_count >= 8:
                bit_count -= 8
                byte_val = (bit_buffer >> bit_count) & 0xFF
                output.append(byte_val)

        if original_len >= 0:
            return bytes(output[:original_len])
        return bytes(output)

    @classmethod
    def serialize_payload(cls, obj: Any, compress: bool = True) -> bytes:
        """Serializes any Python dict/object or string to a Base128 binary payload with length header."""
        raw_json = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        raw_bytes = zlib.compress(raw_json) if compress else raw_json
        
        orig_len = len(raw_bytes)
        packed_data = cls.encode_bytes(raw_bytes)
        
        # Header: 4 bytes big-endian original length + 1 byte compression flag + packed Base128 data
        header = orig_len.to_bytes(4, byteorder="big") + (b"\x01" if compress else b"\x00")
        return header + packed_data

    @classmethod
    def deserialize_payload(cls, data: bytes) -> Any:
        """Deserializes a Base128 binary payload back into a Python dict/object."""
        if len(data) < 5:
            return None
        
        orig_len = int.from_bytes(data[:4], byteorder="big")
        is_compressed = data[4] == 1
        packed_data = data[5:]
        
        raw_bytes = cls.decode_bytes(packed_data, original_len=orig_len)
        if is_compressed:
            raw_bytes = zlib.decompress(raw_bytes)
        
        return json.loads(raw_bytes.decode("utf-8"))
