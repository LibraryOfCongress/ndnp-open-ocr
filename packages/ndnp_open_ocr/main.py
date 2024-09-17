from processors import PDFProcessor, OCRProcessor

# pdf_processor = PDFProcessor(old_pdf='./0833_original.pdf', new_pdf='./0833_new.pdf', postprocessed_pdf='./0833.pdf')
# pdf_processor.transfer_xmp()

ocr_processor = OCRProcessor(input_file_path='./0237.tif', output_path='./output')
ocr_processor.process()
