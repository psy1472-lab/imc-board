import unittest

from infrastructure.upload import sanitize_upload_filename


class UploadSanitizeTests(unittest.TestCase):
    def test_sanitize_keeps_pdf_extension(self):
        self.assertEqual(sanitize_upload_filename("report.pdf"), "report.pdf")

    def test_sanitize_strips_path_and_special_chars(self):
        self.assertEqual(
            sanitize_upload_filename("../../evil name!.pdf"),
            "evil_name.pdf",
        )

    def test_rejects_non_pdf(self):
        with self.assertRaises(ValueError):
            sanitize_upload_filename("report.txt")


if __name__ == "__main__":
    unittest.main()
