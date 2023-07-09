import errno
from bs4 import BeautifulSoup
import exiftool
from rich import print
import subprocess
import os
import logging
import pikepdf
import pytesseract
from PIL import Image

class AltoProcessor:
    def __init__(self, input_file):
        self.input_file = input_file
        with open(input_file, "r") as f:
            content = f.read()
        self.soup = BeautifulSoup(content, "lxml-xml")

    def add_description_tags(self):
        description = self.soup.find("Description")

        software_name = "Tesseract Open Source OCR Engine"
        software_version = "5.2.0-51-ga8735"

        ocr_processing = self.soup.find("OCRProcessing")

        # Replace tesseract library/vendor info... with the tags below
        ocr_processing_step = self.soup.find("ocrProcessingStep")
        if ocr_processing_step is not None:
            processing_software = ocr_processing_step.find(
                "processingSoftware")
            if processing_software is not None:
                software_name_tag = processing_software.find("softwareName")
                if software_name_tag is not None:
                    software_name_tag.string = software_name
                else:
                    software_name_tag = self.soup.new_tag("softwareName")
                    software_name_tag.string = software_name
                    processing_software.append(software_name_tag)

                software_version_tag = processing_software.find(
                    "softwareVersion")
                if software_version_tag is not None:
                    software_version_tag.string = software_version
                else:
                    software_version_tag = self.soup.new_tag("softwareVersion")
                    software_version_tag.string = software_version
                    processing_software.append(software_version_tag)

        # Add postProcessingStep element and its children
        post_processing_step = self.soup.new_tag("postProcessingStep")
        description.append(post_processing_step)

        processing_date_time = self.soup.new_tag("processingDateTime")
        processing_date_time.string = "2023-02-02T15:14:38"
        post_processing_step.append(processing_date_time)

        processing_agency = self.soup.new_tag("processingAgency")
        processing_agency.string = "Library of Congress"
        post_processing_step.append(processing_agency)

        processing_software = self.soup.new_tag("processingSoftware")
        post_processing_step.append(processing_software)

        software_creator = self.soup.new_tag("softwareCreator")
        software_creator.string = "Library of Congress"
        processing_software.append(software_creator)

        software_name = self.soup.new_tag("softwareName")
        software_name.string = "ndnp-open-ocr"
        processing_software.append(software_name)

        software_version = self.soup.new_tag("softwareVersion")
        software_version.string = "1.0"
        processing_software.append(software_version)

        application_description = self.soup.new_tag("applicationDescription")
        application_description.string = "An OCR and PDF reprocessing pipeline developed by Library of Congress for NDNP-specific data including ALTO end-of-line hyphenation substitution, PDF XMP retention, and NDNP batch merging."
        processing_software.append(application_description)

        ocr_processing.append(post_processing_step)

    def convert_pixels_to_inches(self, dpi):
        measurement_unit = self.soup.find("MeasurementUnit")
        measurement_unit.string = "inch1200"

        attributes_to_convert = ["HEIGHT", "WIDTH", "HPOS", "VPOS"]

        def has_required_attrs(element):
            for attr in attributes_to_convert:
                if element.has_attr(attr):
                    return True
            return False

        for element in self.soup.find_all(has_required_attrs):
            for attribute in attributes_to_convert:
                if element.has_attr(attribute):
                    pixel_value = int(element[attribute])
                    inch1200_value = round(float(pixel_value * 1200 / dpi[0]))
                    element[attribute] = str(inch1200_value)

    def fix_alto_file_hyphenation(self):
        # Open the ALTO file.
        try:
            with open(self.filepath, 'r') as f:
                xml = f.read()
                soup = BeautifulSoup(xml, 'xml')

                # Find all TextLines where the content is equal to "Content"
                text_lines = soup.find_all('TextLine')

                for index, line in enumerate(text_lines):
                    hyp_tag = soup.new_tag("HYP", attrs={'CONTENT': '-'})
                    strings = line.find_all('String')

                    # If there are no strings in this line, then there are no hyphens to fix. Exit function in this case.
                    if len(strings) == 0:
                        return
                    last_string = strings[-1]
                    content = last_string.get("CONTENT")

                    # Line-to-Line Hyphenation Check: If the last string ends with a hyphen, it means that there is a linebreak and the other portion of the hyphenation is in the next line
                    if content.endswith('-') and len(content) > 1:
                        next_line = text_lines[index + 1]
                        next_line_string = next_line.find_all('String')[0]

                        # Insert HypTag at end of last_string line
                        line.append(hyp_tag)
                        last_string['CONTENT'] = last_string.get(
                            "CONTENT").replace('-', '')
                        combined_word = last_string.get(
                            "CONTENT") + next_line_string.get("CONTENT")
                        last_string['SUBS_CONTENT'] = combined_word
                        next_line_string['SUBS_CONTENT'] = combined_word
                        last_string['SUBS_TYPE'] = 'HypPart1'
                        next_line_string['SUBS_TYPE'] = 'HypPart2'

                f.close()

                # Overwrite old ALTO file with the new and fixed XML contents.
                with open(self.filepath, 'w') as f:
                    f.write(str(soup))
                    f.close()
        except Exception as e:
            print("ALTO file hyphenation fix failed: {}".format(e))

    def save(self, output_file):
        with open(output_file, "w") as f:
            f.write(str(self.soup))


class PDFProcessor:
    def __init__(self, old_pdf, new_pdf):
        self.old_pdf = old_pdf
        self.new_pdf = new_pdf

    def transfer_xmp(self):
        print(f"Transferring XMP data from {self.old_pdf} to {self.new_pdf}")
        try:
            with exiftool.ExifToolAlpha() as et:
                new_tags = et.get_tags(self.new_pdf, tags=None)[0]
                et.copy_tags(self.old_pdf, self.new_pdf)
                old_tags = et.get_tags(self.old_pdf, tags=None)[0]

                title_tag = None
                title_key_list = list(
                    filter(lambda x: x.startswith('XMP:Title'), old_tags))
                if len(title_key_list) >= 1:
                    title_tag = old_tags[title_key_list[0]]

                if title_tag:
                    et.set_tags(self.new_pdf, {
                                'Title': title_tag, "XMP:Title-en": title_tag})

                et.set_tags(self.new_pdf, {
                    'XMP:CreateDate': new_tags['File:FileModifyDate'][0:14],
                    'XMP:ModifyDate': new_tags['File:FileModifyDate'][0:14],
                    'PDF:CreateDate': new_tags['File:FileModifyDate'][0:14],
                    'PDF:ModifyDate': new_tags['File:FileModifyDate'][0:14],
                    'PDF:Producer': new_tags['PDF:Producer']
                }
                )
        except Exception as e:
            print(
                f"Failure transferring XMP data from {self.old_pdf} to {self.new_pdf}: {e}")
            return False

    def postprocess_pdf(self):
        args = [
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-dFastWebView=true",
            f"-sOutputFile={self.new_pdf}",
            "-sDEVICE=pdfwrite",
            "-dDownsampleColorImages=true",
            "-dDownsampleGrayImages=true",
            "-dDownsampleMonoImages=true",
            "-dColorImageResolution=150",
            "-dGrayImageResolution=150",
            "-dMonoImageResolution=150",
            "-dColorImageDownsampleThreshold=1.0",
            "-dGrayImageDownsampleThreshold=1.0",
            "-dMonoImageDownsampleThreshold=1.0",
            "-dProcessDSCComments=false",
            self.old_pdf,
            "pdf_marks.txt"
        ]

        result = subprocess.run(args, check=True)
        print("stdout:", result.stdout)
        print("stderr:", result.stderr)

        if os.path.isfile(self.new_pdf):
            print(f"Output file exists and is a regular file: {self.new_pdf}")
        else:
            print("Output file does not exist or is not a regular file.")


class OCRProcessor:
    def __init__(self, input_file_path, output_path):
        self.input_file_path = input_file_path
        self.output_path = output_path

    def _get_file_name(self):
        return os.path.splitext(os.path.basename(self.input_file_path))[0]

    def _get_new_pdf_path(self):
        return os.path.join(self.output_path, f"{self._get_file_name()}_output.pdf")

    def _get_postprocessed_pdf_path(self):
        return os.path.join(self.output_path, f"{self._get_file_name()}.pdf")

    def _get_alto_file_path(self):
        return os.path.join(self.output_path, f"{self._get_file_name()}.xml")

    def generate_pdf(self):
        try:
            pdf = pytesseract.image_to_pdf_or_hocr(self.input_file_path, extension="pdf")
            logging.info("NEW PDF", self._get_new_pdf_path())
            with open(self._get_new_pdf_path(), "w+b") as f:
                f.write(pdf)
            del pdf
        except Exception as e:
            logging.error(f"PDF generation failed: {self._get_file_name()} {e}")

    def postprocess_pdf(self):
        processor = PDFProcessor(self._get_new_pdf_path(), self._get_postprocessed_pdf_path())
        processor.postprocess_pdf()
        processor.transfer_xmp()

    def linearize_pdf(self):
        try:
            with pikepdf.Pdf.open(self._get_postprocessed_pdf_path(), allow_overwriting_input=True) as pdf:
                pdf.save(self._get_postprocessed_pdf_path(), linearize=True)
        except Exception as e:
            logging.error(f"PDF Linearization failed: {self._get_file_name()} {e}")

    def generate_alto(self):
        try:
            logging.info("TRY TO GENERATE ALTO")
            xml = pytesseract.image_to_alto_xml(self.input_file_path)
            with open(self._get_alto_file_path(), "w+b") as f:
                f.write(xml)

            image = Image.open(self.input_file_path)
            dpi = image.info.get("dpi", (96, 96))

            logging.info(dpi)

            alto_processor = AltoProcessor(self._get_alto_file_path())
            alto_processor.add_description_tags()
            alto_processor.convert_pixels_to_inches(dpi)
            alto_processor.save(self._get_alto_file_path())
            del xml
        except Exception as e:
            logging.error(f"ALTO generation failed: {self._get_file_name()} {e}")

    def process(self):
        def list_directory_contents(directory_path):
            """List the contents of the directory"""
            directory_contents = os.listdir(directory_path)
            logging.info(f"Contents of {directory_path}:")
            for item in directory_contents:
                logging.info(f" - {item}")

        def make_directory(path):
            """Create a directory if it doesn't exist"""
            try:
                os.makedirs(path)
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
            list_directory_contents(os.path.dirname(self.input_file_path))
            make_directory(self.output_path)
            logging.info("TEMP IMAGE PATH", self.input_file_path)

        self.generate_pdf()
        self.postprocess_pdf()
        self.linearize_pdf()
        self.generate_alto()

        os.remove(self._get_new_pdf_path())
        # Remove pikePdf .pdf_original file output
        os.remove(os.path.join(self.output_path, self._get_file_name() + ".pdf_original"))


# if __name__ == "__main__":
#     processor = OCRProcessor(input_file_path="/Users/dillonpeterson/Library/CloudStorage/OneDrive-StandardData/LOC_Bathces/notvalidated/batch_dlc_sampleissue/2010270501/00237285074/1203.tif", output_path="./")
#     processor.process()
#     print("Job Complete")