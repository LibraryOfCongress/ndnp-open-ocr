from processors import PDFProcessor

pdf_processor = PDFProcessor(old_pdf='./0833_original.pdf', new_pdf='./0833_new.pdf', postprocessed_pdf='./0833.pdf')
pdf_processor.transfer_xmp()