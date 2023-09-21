from processors import OCRProcessor, PDFProcessor, PreprocessingMethod

if __name__ == "__main__":
    processor = OCRProcessor(
        input_file_path="/Users/dillonpeterson/LOC_Batches/notvalidated2//Users/dillonpeterson/LOC_Batches/notvalidated2/batch_dlc_sampleissue/2010270501/00237285074/0187.tif",
        output_path="./",
        preprocessing_method=PreprocessingMethod.ORIGINAL,
    )
    processor.generate_pdf()
    # processor = OCRProcessor(
    #     input_file_path="/Volumes/DLP1/batch_dlc_kite_ver19/data/sn83030214/00206531290/0001.tif",
    #     output_path="./",
    #     preprocessing_method=PreprocessingMethod.ADAPTIVE,
    # )
    # processor.generate_pdf()
    # processor.transfer_xmp()
    # processor = PDFProcessor(
    #     old_pdf='/Volumes/DLP1/batch_dlc_kite_ver18/data/sn83030214/00206531290/1877050301/0021.pdf',  # original PDF
    #     new_pdf='./0021_new.pdf',  # new PDF
    #     postprocessed_pdf='./0021.pdf'  # where to save final PDF, after all post-processing steps are complete.
    # )

    # processor.transfer_xmp()

    print("Job Complete")
