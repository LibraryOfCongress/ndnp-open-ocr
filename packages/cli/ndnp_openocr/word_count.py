import argparse
import logging
import os
import xml.sax
from collections import defaultdict
from multiprocessing import Pool, cpu_count
import xml.etree.ElementTree as ET
import re


class AltoParser(xml.sax.ContentHandler):
    def __init__(self, local_word_count):
        super().__init__()
        self.current_segment = None
        self.local_word_count = local_word_count

    def startElement(self, tag, attrs):
        if tag.lower() == 'string':
            content = attrs.get('CONTENT')
            if content:
                self.local_word_count[content] += 1

    def parse(self, file_path):
        self.current_segment = file_path
        with open(file_path, 'r') as f:
            raw = f.read().replace('xmlns="http://www.loc.gov/standards/alto/ns-v2#"', '')
        xml.sax.parseString(raw, self)

def get_namespace(element):
    """This function gets the namespace of the root element
    for a xml document (e.g. xmlns).

    For whatever reason the python xml lib doesn't
    handle namespaces see:
    https://stackoverflow.com/questions/13412496/python-elementtree-module-how-to-ignore-the-namespace-of-xml-files-to-locate-ma # noqa: E501

    The ET.parser() will print namespaced tags
    as {namespace}tag so we simply use regex to
    find find namespace.

    """
    m = re.match(r'\{.*\}', element.tag)
    return m.group(0) if m else ''

def get_batch_info(path_to_batch):
    """Parses the batch.xml file to find the infomation about the batch.

    This includes: The lccn, issue, date, edition and path to the xml file
    containing the list of alto files.

    This info is included in the issue elements in the batch.xml document.

    returns a list of dictionaries with the following structure:
    ```
    {
        'lccn': 'sn87057934',
        'date': {
            'month': '05',
            'day': '04',
            'year': '1911'
        },
        'alto_files': [
            'test_files/batch_iahi_miller_ver02/data/sn87057934/00415622697/1911050401/0560.xml',
            'test_files/batch_iahi_miller_ver02/data/sn87057934/00415622697/1911050401/0561.xml',
            'test_files/batch_iahi_miller_ver02/data/sn87057934/00415622697/1911050401/0562.xml'
        ],
        'edition': '1'
    }
    ```
    """
    batch_info = []

    batch_aliases = [
        'batch_1.xml',
        'BATCH_1.xml',
        'batchfile_1.xml',
        'batch_2.xml',
        'BATCH_2.xml',
        'batch.xml'
    ]

    batch_xml_file = None
    for alias in batch_aliases:
        if os.path.isfile(
            os.path.join(
                path_to_batch,
                'data/',
                alias
            )
        ):
            batch_xml_file = os.path.join(
                path_to_batch,
                'data/',
                alias
            )
            break

    if batch_xml_file is None:
        logging.warning(
            'No batch.xml file found for : %s', path_to_batch
        )
        return []

    root = ET.parse(batch_xml_file).getroot()
    namespace = get_namespace(root)
    for issue in root.findall(namespace + 'issue'):
        batch_dict = {}
        batch_dict['lccn'] = issue.get('lccn')
        date = issue.get('issueDate').split('-')
        batch_dict['date'] = {
            'year': date[0],
            'month': date[1],
            'day': date[2]
        }
        batch_dict['edition'] = issue.get('editionOrder')
        issue_xml_file = issue.text.strip('/').strip('./')
        issue_xml_file = os.path.join(path_to_batch, 'data', issue_xml_file)
        # file_list = issue.text.replace('./', path_to_batch + '/data/')
        batch_dict['alto_files'] = get_alto_files(issue_xml_file)
        batch_info.append(batch_dict)
    return batch_info


def get_alto_files(issue_xml):
    """Parses the xml containing the file contents
    for a specific lccn + date + edition

    The file is searched for the fileSec element.
    In this tag exisit fileGroup elements
    which each contain a list of file elements.
    The contents of the file element is
    parsed to retrieve the ocr location.
    """
    working_dir, _ = os.path.split(issue_xml)
    alto_files = []
    root = ET.parse(issue_xml).getroot()
    namespace = get_namespace(root)

    fileSec = root.find(namespace + 'fileSec')

    # sometimes the file does not contain a filSec element
    if fileSec is None:
        return []

    for file_group in fileSec:
        for f in file_group:
            if f.get('USE') == 'ocr':
                flocat = f.find(namespace + 'FLocat')
                ocr_name = flocat.get(
                    '{http://www.w3.org/1999/xlink}href'
                ).replace('./', '')
                alto_files.append(
                    os.path.join(working_dir, ocr_name)
                )
    return alto_files

def process_alto(file_path):
    local_word_count = defaultdict(int)
    parser = AltoParser(local_word_count)
    parser.parse(file_path)
    return dict(local_word_count)

def main(batch_dir):
    batch_content = get_batch_info(batch_dir)
    # print("BATCH CONTENT: %s", batch_content)
    alto_files = []
    for issue in batch_content:
        alto_files += issue['alto_files']
    print(f"Alto file count: {len(alto_files)}")
    if not alto_files:
        logging.warning('No ALTO XML files found in the directory: %s', batch_dir)
        return

    with Pool(processes=cpu_count()) as pool:
        results = pool.map(process_alto, alto_files)
        
    word_count = defaultdict(int)
    for local_count in results:
        for word, count in local_count.items():
            word_count[word] += count


    print(f'Total unique words: {len(word_count)}')

if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser(description='Count unique words in ALTO XML files')
    parser.add_argument('batch_dir', help='Directory containing ALTO XML files', type=str)
    args = parser.parse_args()

    main(args.batch_dir)
