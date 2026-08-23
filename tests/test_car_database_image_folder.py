import os
import tempfile
import unittest

from car_database import CarDatabase


class CarImageFolderTests(unittest.TestCase):
    def make_database(self, image_directory):
        database = CarDatabase.__new__(CarDatabase)
        database.set_image_directory(image_directory)
        return database

    def test_resolves_sku_case_insensitively_in_selected_folder(self):
        with tempfile.TemporaryDirectory() as image_directory:
            image_path = os.path.join(image_directory, "JBB14.webp")
            with open(image_path, "wb") as image_file:
                image_file.write(b"image")

            database = self.make_database(image_directory)
            resolved_path = database.resolve_car_image_path({"sku": "jbb14"})

            self.assertEqual(resolved_path, os.path.abspath(image_path))

    def test_prefers_webp_when_multiple_supported_formats_exist(self):
        with tempfile.TemporaryDirectory() as image_directory:
            png_path = os.path.join(image_directory, "ABC01.png")
            webp_path = os.path.join(image_directory, "ABC01.webp")
            for image_path in (png_path, webp_path):
                with open(image_path, "wb") as image_file:
                    image_file.write(b"image")

            database = self.make_database(image_directory)
            resolved_path = database.resolve_car_image_path({"sku": "ABC01"})

            self.assertEqual(resolved_path, os.path.abspath(webp_path))

    def test_falls_back_to_stored_filename_inside_selected_folder(self):
        with tempfile.TemporaryDirectory() as image_directory:
            image_path = os.path.join(image_directory, "custom-poster.jpg")
            with open(image_path, "wb") as image_file:
                image_file.write(b"image")

            database = self.make_database(image_directory)
            resolved_path = database.resolve_car_image_path({
                "sku": "MISSING",
                "image": "car_images/custom-poster.jpg"
            })

            self.assertEqual(resolved_path, os.path.abspath(image_path))

    def test_returns_empty_path_when_selected_folder_has_no_match(self):
        with tempfile.TemporaryDirectory() as image_directory:
            database = self.make_database(image_directory)

            self.assertEqual(
                database.resolve_car_image_path({"sku": "UNKNOWN", "image": "car_images/UNKNOWN.webp"}),
                ""
            )


if __name__ == "__main__":
    unittest.main()
