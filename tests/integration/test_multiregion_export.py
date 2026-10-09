from pathlib import Path

from PIL import Image

from conftest import publish_fixture
from papervault.exporting import export_assets
from papervault.library import encode


def test_multi_page_png_exports_every_region_at_requested_dpi(library):
    source = Path(__file__).parents[1] / "fixtures" / "geometry.pdf"
    paper, _ = library.import_file(source)
    resource = publish_fixture(library, paper["id"])
    locations = [{"page_index": 0, "bbox": [101, 131, 179, 189]},
                 {"page_index": 2, "bbox": [211, 281, 264, 349]}]
    with library.db.transaction() as con:
        row = con.execute("SELECT auto_json FROM resources WHERE id=?", (resource["id"],)).fetchone()
        import json
        data = json.loads(row[0])
        data["locations"] = locations
        con.execute("UPDATE resources SET auto_json=? WHERE id=?", (encode(data), resource["id"]))
    result = export_assets(library, [], [resource["id"]], "png", 150)
    with Image.open(result) as image:
        red = image.getpixel((100, 100))
        blue = image.getpixel((100, image.height-100))
        assert red[0] > 220 and red[2] < 100
        assert blue[2] > 200 and blue[0] < 100
        assert image.height > 500
