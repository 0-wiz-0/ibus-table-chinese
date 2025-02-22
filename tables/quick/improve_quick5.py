#!/usr/bin/python3
#
# Copyright (c) 2021 Mike FABIAN <mfabian@redhat.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>
'''
Improves the quick5.txt table to resolve:

https://github.com/mike-fabian/ibus-table-chinese/issues/4

For all lines starting with x check whether there is another line
containing the same Chinese character with an input not starting
with x. If such a line exists, change the priority from 1000 to
900.
'''

from typing import Any
from typing import List
from typing import Dict
import re
import unicodedata
import urllib.request
import logging

IMPORT_CHINESE_VARIANTS_SUCCESSFUL = False
try:
    import chinese_variants
    IMPORT_CHINESE_VARIANTS_SUCCESSFUL = True
except (ImportError,):
    IMPORT_CHINESE_VARIANTS_SUCCESSFUL = False

def parse_args() -> Any:
    '''Parse the command line arguments'''
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            'Generate a script containing a table and a function '
            + 'to check whether a string of Chinese characters '
            + 'is simplified or traditional'))
    parser.add_argument('-i', '--inputfilename',
                        nargs='?',
                        type=str,
                        default='quick5.txt',
                        help='input file, default is %(default)s')
    parser.add_argument('-o', '--outputfilename',
                        nargs='?',
                        type=str,
                        default='quick5.txt.new',
                        help='output file, default is %(default)s')
    parser.add_argument('-d', '--debug',
                        action='store_true',
                        help='print debugging output')
    return parser.parse_args()

def big5_code(phrase: str) -> bytes:
    '''
    Encode a string in Big5 or, if that is not possible,
    return something higher than any Big5 code.

    :param phrase: String to be encoded in Big5 encoding
    '''
    try:
        big5 = phrase.encode('Big5')
    except UnicodeEncodeError:
        big5 = b'\xff\xff' # higher than any Big5 code
    return big5

def improve_quick5(inputfilename: str, outputfilename: str) -> None:
    '''
    Read the quick5.txt file and write an improved version
    '''
    head: List[str] = []
    tail: List[str] = []
    table: Dict[Tuple[str, str], int] = {}
    reading_head = True
    reading_table = True
    reading_tail = True
    with open(inputfilename, 'r') as inputfile:
        logging.info("input file=%s", inputfile)
        for line in inputfile:
            if reading_head and not line.startswith('BEGIN_TABLE'):
                head.append(line)
                continue
            if reading_head:
                logging.info('Header read.')
                head.append('BEGIN_TABLE\n')
                reading_head = False
                continue
            if reading_table and not line.startswith('END_TABLE'):
                stripped_line = line.strip().split('\t')
                if len(stripped_line) < 4:
                    stripped_line.append('')
                (input,
                 chinese_character,
                 weight,
                 comment) = stripped_line
                if (input, chinese_character) in table:
                    first_weight = table[(input, chinese_character)]['weight']
                    logging.warning(
                        'duplicate %s %s first weight=%s second weight=%s',
                        input, chinese_character,
                        first_weight, weight)
                    table[(input, chinese_character)]['weight'] = max(
                        int(weight), int(first_weight))
                    continue
                table[(input, chinese_character)] = {
                    'weight': int(weight),
                    'comment':  comment,
                    }
                continue
            if reading_table:
                logging.info('Table read.')
                reading_table = False
            tail.append(line)
    for (input, chinese_character) in table:
        unicode_name = unicodedata.name(chinese_character, '')
        if unicode_name.startswith('CJK COMPATIBILITY IDEOGRAPH'):
            unicode_decomposition = unicodedata.decomposition(
                chinese_character)
            unicode_decomposition_char = ''
            if unicode_decomposition:
                unicode_decomposition_char = chr(
                    int(unicode_decomposition, 16))
            logging.info('%s\t%s\t%s %s %s %s',
                         input,
                         chinese_character,
                         table[(input, chinese_character)]['weight'],
                         unicode_name,
                         unicode_decomposition,
                         unicode_decomposition_char)
        if IMPORT_CHINESE_VARIANTS_SUCCESSFUL:
            number_of_problems_with_chinese_variants: int = 0
            category = chinese_variants.detect_chinese_category(
                chinese_character)
            if category == 1:
                used_in_taiwan = False
                utf8_for_url = ''
                for byte in chinese_character.encode('utf-8'):
                    utf8_for_url += f'%{byte:X}'
                url = (f'https://dict.revised.moe.edu.tw/'
                       f'search.jsp?md=1&word={utf8_for_url}#searchL')
                with urllib.request.urlopen(url) as f:
                    page = f.read().decode('utf-8')
                    if page and '查無資料' not in page:
                        used_in_taiwan = True
                if used_in_taiwan:
                    number_of_problems_with_chinese_variants += 1
                    logging.info(
                        'Classified as simplified only: %s\t%s\tused_in_taiwan=%s',
                        input, chinese_character, repr(used_in_taiwan))
        if input.startswith('x'):
            valid_input_chars_without_x = 'abcdefghijklmnopqrstuvwyz'
            for input1 in valid_input_chars_without_x:
                if (input1, chinese_character) in table:
                    table[(input1, chinese_character)]['weight'] = 900
                for input2 in valid_input_chars_without_x:
                    if (input1 + input2, chinese_character) in table:
                        table[(input1 + input2, chinese_character)]['weight'] = 900
    if IMPORT_CHINESE_VARIANTS_SUCCESSFUL:
        logging.info(
            'number_of_problems_with_chinese_variants=%s',
            number_of_problems_with_chinese_variants)
    with open(outputfilename, 'w') as outputfile:
        logging.info("output file=%s", outputfile)
        for line in head:
            outputfile.write('%s' % line)
        for ((input, chinese_character), value) in sorted(table.items(),
                                                   key=lambda x: (
                                                       x[0][0],
                                                       -x[1]['weight'],
                                                       ord(x[0][1]), # Unicode code point
                                                   )):
            if value['comment']:
                outputfile.write('%s\t%s\t%s\t%s\n'
                                 % (input, chinese_character, value['weight'],
                                    value['comment']))
            else:
                outputfile.write('%s\t%s\t%s\n'
                                 % (input, chinese_character, value['weight']))
        for line in tail:
            outputfile.write('%s' % line)

def main() -> None:
    '''Main program'''
    args = parse_args()
    log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)
    improve_quick5(args.inputfilename, args.outputfilename)

if __name__ == '__main__':
    main()
