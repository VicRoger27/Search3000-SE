import tempfile
import unittest
from engine.crawler.pure_spider import PureWebSpider
from engine.storage.disk_index import DiskIndexStore


class TestPureSpider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = DiskIndexStore(base_dir=self.temp_dir.name)
        self.spider = PureWebSpider(store=self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_page_data_and_outlinks(self):
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head><title>YOLO vs SAM Comparison</title></head>
        <body>
            <h1>Computer Vision</h1>
            <p>YOLO is for fast object detection, while SAM is for promptable image segmentation.</p>
            <a href="/wiki/Object_detection">Object Detection</a>
            <a href="https://example.org/segment_anything">SAM Project</a>
            <a href="/image.png">Ignore image</a>
        </body>
        </html>
        """
        extracted = self.spider.extract_page_data(sample_html, base_url="https://example.org/article")
        self.assertEqual(extracted["title"], "YOLO vs SAM Comparison")
        self.assertIn("YOLO is for fast object detection", extracted["text"])
        self.assertEqual(len(extracted["outlinks"]), 2)
        self.assertIn("https://example.org/wiki/Object_detection", extracted["outlinks"])
        self.assertIn("https://example.org/segment_anything", extracted["outlinks"])
        # Image should be filtered out
        self.assertFalse(any(l.endswith(".png") for l in extracted["outlinks"]))


if __name__ == "__main__":
    unittest.main()
