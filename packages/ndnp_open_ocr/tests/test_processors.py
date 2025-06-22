import os
import sys
import types
import tempfile
from unittest import mock

# Provide dummy segmenter module to satisfy import in processors
segmenter_dummy = types.ModuleType('ndnp_open_ocr.segmenter')
segmenter_dummy.segment_page = lambda x: ([], [])
segmenter_dummy.merge_alto_region_xmls = lambda **kwargs: None
sys.modules['ndnp_open_ocr.segmenter'] = segmenter_dummy

# Provide dummy hocker module to avoid heavy dependency
hocker_dummy = types.ModuleType('hocker')
sys.modules['hocker'] = hocker_dummy

from ndnp_open_ocr.processors import AltoProcessor, OCRProcessor

SAMPLE_ALTO = os.path.join(os.path.dirname(__file__), 'assets', 'sample_alto.xml')


def test_add_description_tags(monkeypatch):
    monkeypatch.setattr('pytesseract.get_tesseract_version', lambda: '5.0')
    processor = AltoProcessor(SAMPLE_ALTO)
    processor.add_description_tags()
    assert processor.soup.find('postProcessingStep') is not None
    software_name = processor.soup.find_all('softwareName')[-1].string
    assert software_name == 'ndnp-open-ocr'


def test_convert_pixels_to_inches():
    processor = AltoProcessor(SAMPLE_ALTO)
    processor.convert_pixels_to_inches((300, 300))
    assert processor.soup.find('MeasurementUnit').string == 'inch1200'
    page = processor.soup.find('Page')
    assert page['WIDTH'] == '1200'
    assert page['HEIGHT'] == '1600'


def test_fix_alto_file_hyphenation():
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as tmp:
        tmp.write(open(SAMPLE_ALTO).read())
    proc = AltoProcessor(tmp.name)
    proc.fix_alto_file_hyphenation()
    strings = proc.soup.find_all('String')
    assert strings[1]['SUBS_CONTENT'] == 'WorldAgain'
    assert strings[1]['SUBS_TYPE'] == 'HypPart1'
    os.unlink(tmp.name)


def test_get_postprocessed_pdf_path(tmp_path):
    tiff = tmp_path / 'file.tif'
    tiff.write_bytes(b'')
    processor = OCRProcessor(str(tiff), str(tmp_path))
    expected = tmp_path / 'file.pdf'
    assert processor.get_postprocessed_pdf_path() == str(expected)
