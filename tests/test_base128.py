import unittest
from engine.storage.base128 import Base128Codec


class TestBase128(unittest.TestCase):
    def test_encode_decode_bytes(self):
        sample = b"Search3000 to rival Google! With Spark-X 2.6 on GPU."
        encoded = Base128Codec.encode_bytes(sample)
        # All bytes in encoded must be in 0..127
        self.assertTrue(all(0 <= b <= 127 for b in encoded))
        decoded = Base128Codec.decode_bytes(encoded, original_len=len(sample))
        self.assertEqual(decoded, sample)

    def test_serialize_deserialize_payload(self):
        doc = {
            "url": "https://en.wikipedia.org/wiki/Search_engine",
            "title": "Search Engine - Wikipedia",
            "snippet": "A search engine is an information retrieval software system...",
            "keywords": ["search", "engine", "google", "retrieval", "index"],
            "rank_score": 0.9842,
        }
        serialized = Base128Codec.serialize_payload(doc)
        restored = Base128Codec.deserialize_payload(serialized)
        self.assertEqual(restored, doc)


if __name__ == "__main__":
    unittest.main()
