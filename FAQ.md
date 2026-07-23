# Frequently Asked Questions

- In a nutshell, how does this software work?
  - This pipeline essentially takes the images (TIFFs or JP2s) and select metadata (XMP from PDFs) from existing NDNP-structured batches as input to create new ALTO XML and PDF files. Once the infrastructure is set up, a user will interact with the pipeline using a command line interface (CLI) to "process" the input files and "sync" the new output files with the original batch. The idea is that the workflow begins with an old NDNP batch and ends with a new NDNP batch.

- What input formats will the pipeline require?
  - NDNP-Open-OCR is customized for [NDNP style batches](https://www.loc.gov/ndnp/) but has some built-in flexibility. It can take TIFF, JPEG2000, and JPEG files as input. By default, the pipeline also requires an NDNP-spec PDF from which it grabs the pre-existing XMP. If a PDF is missing, however, the pipeline will simply skip the XMP extraction and continue processing.

- We have digitized newspaper data files that only partially meet NDNP specifications. Does the pipeline only work for NDNP batches?
  - No, while there is a good deal of customization around working with NDNP data, there are ways to make this pipeline work for other formats. For example, the main two functions of the workflow when using the CLI are the "process" command and the "sync" command. The "process" workflow takes an image as input, runs it though the pipeline, and produces new ALTO XML and PDF files. The "sync" command takes the output from the "process" command and syncs that with an existing NDNP batch structure. One could choose not to use the default "sync" command. Some users might opt to fork the code, customize for a non-NDNP workflow, and share for others.

- Does NDNP-Open-OCR handle non-English text?
  - The latest version of NDNP-Open-OCR has only been tested with English-language newspapers, because the content that we are currently reprocessing is all English. The Library's NDNP-Open-OCR team hopes to utilize Tesseract's built-in multi-lingual capabilities in the future. With a few minor adjustments, the pipeline should be able to handle other languages. We encourage contributions in this area.

- How does this pipeline differ from a standard OCR generation solution?
  - This OCR processing pipeline has been optimized for historical U.S. newspapers and is cost-effective to run. It doesn't require a license to use since it is an open-source product. As mentioned in the repository's README, historical newspapers are complex documents with a variety of page and column layouts that can be challenging for OCR engines to parse. NDNP-Open-OCR includes an option to use an advanced segmentation setting that more accurately identifies columns, text, and other regions on historical newspaper scans. This setting incorporates newspaper layout detection modeling from the American Stories (Harvard) dataset. [Read more about Harvard's American Stories project here](https://dell-research-harvard.github.io/resources/americanstories).

    To use the enhanced segmentation features in NDNP-Open-OCR, use the `--segmentation` flag with the CLI "process" command. If this flag is not used, Tesseract's generalized layout detection model will be used.
    The Library of Congress team presented on the inclusion of American Stories. [Check out these resources](https://guides.loc.gov/chronicling-america/improved-text#s-lib-ctab-34250734-2) for more information.

- Can this be installed locally or does it require use of cloud-based services?
  - While the pipeline has been optimized within the Library of Congress using cloud-based infrastructure, it can technically be run locally. However, the local pipeline is intended for testing and experimentation. It is too slow for full production workloads. The tradeoff of running locally will be significantly lower efficiency from start to end. An average NDNP batch (~4,000 pages) may take several weeks to run in a local environment as compared to a couple of hours in a cloud-based deployment.
