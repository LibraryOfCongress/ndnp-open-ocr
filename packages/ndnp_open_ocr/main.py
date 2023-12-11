import processors

OCRProcessor = processors.OCRProcessor('./test/0249.tif', './')
OCRProcessor.generate_alto()