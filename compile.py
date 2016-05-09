#!/usr/bin/env python

# Copyright (C) 2016  Alex Yatskov <alex@foosoft.net>
# Author: Alex Yatskov <alex@foosoft.net>
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
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import codecs
import sqlite3
import json
import optparse
import os.path
import re


PARSED_TAGS = {
    'Buddh',
    'MA',
    'X',
    'abbr',
    'adj',
    'adj-f',
    'adj-i',
    'adj-na',
    'adj-no',
    'adj-pn',
    'adj-t',
    'adv',
    'adv-n',
    'adv-to',
    'arch',
    'ateji',
    'aux',
    'aux-adj',
    'aux-v',
    'c',
    'chn',
    'col',
    'comp',
    'conj',
    'ctr',
    'derog',
    'eK',
    'ek',
    'exp',
    'f',
    'fam',
    'fem',
    'food',
    'g',
    'geom',
    'gikun',
    'gram',
    'h',
    'hon',
    'hum',
    'iK',
    'id',
    'ik',
    'int',
    'io',
    'iv',
    'ling',
    'm',
    'm-sl',
    'male',
    'male-sl',
    'math',
    'mil',
    'n',
    'n-adv',
    'n-pref',
    'n-suf',
    'n-t',
    'num',
    'oK',
    'obs',
    'obsc',
    'ok',
    'on-mim',
    'P',
    'p',
    'physics',
    'pn',
    'poet',
    'pol',
    'pr',
    'pref',
    'prt',
    'rare',
    's',
    'sens',
    'sl',
    'st',
    'suf',
    'u',
    'uK',
    'uk',
    'v1',
    'v2a-s',
    'v4h',
    'v4r',
    'v5',
    'v5aru',
    'v5b',
    'v5g',
    'v5k',
    'v5k-s',
    'v5m',
    'v5n',
    'v5r',
    'v5r-i',
    'v5s',
    'v5t',
    'v5u',
    'v5u-s',
    'v5uru',
    'v5z',
    'vi',
    'vk',
    'vn',
    'vs',
    'vs-c',
    'vs-i',
    'vs-s',
    'vt',
    'vulg',
    'vz'
}


def is_hiragana(c):
    return 0x3040 <= ord(c) < 0x30a0


def is_katakana(c):
    return 0x30a0 <= ord(c) < 0x3100


def load_definitions(path):
    print('Parsing "{0}"...'.format(path))
    with codecs.open(path, encoding='euc-jp') as fp:
        return filter(lambda x: x and x[0] != '#', fp.read().splitlines())


def parse_kanjidic(path):
    results = {}
    for line in load_definitions(path):
        segments = line.split()
        character = segments[0]
        kunyomi = ' '.join(filter(lambda x: list(filter(is_hiragana, x)), segments[1:]))
        onyomi = ' '.join(filter(lambda x: list(filter(is_katakana, x)), segments[1:]))
        glossary = re.findall('\{([^\}]+)\}', line)
        results[character] = (kunyomi or None, onyomi or None, glossary)

    return results


def parse_edict(path):
    results = []
    for line in load_definitions(path):
        segments = line.split('/')

        exp_parts = segments[0].split(' ')
        expression = exp_parts[0]
        reading_match = re.search('\[([^\]]+)\]', exp_parts[1])
        reading = None if reading_match is None else reading_match.group(1)

        defs = []
        tags = set()

        for index, dfn in enumerate(filter(None, segments[1:])):
            dfn_match = re.search(r'^((?:\((?:[\w\-\,\:]*)*\)\s*)*)(.*)$', dfn)

            tags_raw = set(filter(None, re.split(r'[\s\(\),]', dfn_match.group(1))))
            tags_raw = tags_raw.intersection(PARSED_TAGS)
            tags = tags.union(tags_raw)

            gloss = dfn_match.group(2).strip()
            if len(gloss) == 0:
                continue

            if index == 0 or len(dfn_match.group(1)) > 0:
                defs.append([gloss])
            else:
                defs[-1].append(gloss)

        result = [expression, reading, ' '.join(tags)]
        result += map(lambda x: '; '.join(x), defs)

        results.append(result)

    indices = {}
    for i, d in enumerate(results):
        for key in d[:2]:
            if key is not None:
                values = indices.get(key, [])
                values.append(i)
                indices[key] = values

    return {'defs': results, 'indices': indices}


def output_dict_json(output_dir, input_file, parser):
    if input_file is not None:
        base = os.path.splitext(os.path.basename(input_file))[0]
        with open(os.path.join(output_dir, base) + '.json', 'w') as fp:
             json.dump(parser(input_file), fp, separators=(',', ':'))


def build_db_json(dict_dir, kanjidic, edict, enamdict):
    if kanjidic is not None:
        output_dict_json(dict_dir, kanjidic, parse_kanjidic)
    if edict is not None:
        output_dict_json(dict_dir, edict, parse_edict)
    if enamdict is not None:
        output_dict_json(dict_dir, enamdict, parse_edict)


def output_edict_sqlite(cursor, definitions):
    cursor.execute('CREATE TABLE IF NOT EXISTS Vocab(id INTEGER PRIMARY KEY, expression TEXT, reading TEXT, tags TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS VocabGloss(glossary TEXT, vocabId INTEGER, FOREIGN KEY(vocabId) REFERENCES Vocab(id))')

    for expression, reading, tags, *glossary in definitions:
        cursor.execute('INSERT INTO Vocab VALUES(?, ?, ?, ?)', (None, expression, reading, tags))
        vocabId = cursor.lastrowid
        for gloss in glossary:
            cursor.execute('INSERT INTO VocabGloss VALUES(?, ?)', (gloss, vocabId))


def output_kanjidic_sqlite(cursor, definitions):
    cursor.execute('CREATE TABLE IF NOT EXISTS Kanji(id INTEGER PRIMARY KEY, character TEXT, kunyomi TEXT, onyomi TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS KanjiGloss(glossary TEXT, kanjiId INTEGER, FOREIGN KEY(kanjiId) REFERENCES Kanji(id))')

    for character, (kunyomi, onyomi, glossary) in definitions.items():
        cursor.execute('INSERT INTO Kanji VALUES(?, ?, ?, ?)', (None, character, kunyomi, onyomi))
        kanjiId = cursor.lastrowid
        for gloss in glossary:
            cursor.execute('INSERT INTO KanjiGloss VALUES(?, ?)', (gloss, kanjiId))


def build_db_sqlite(db_path, kanjidic, edict, enamdict):
    os.remove(db_path)

    with sqlite3.connect(db_path) as db:
        cursor = db.cursor()
        if kanjidic is not None:
            output_kanjidic_sqlite(cursor, parse_kanjidic(kanjidic))
        if edict is not None:
            output_edict_sqlite(cursor, parse_edict(edict)['defs'])
        if enamdict is not None:
            output_edict_sqlite(cursor, parse_edict(enamdict))


def main():
    parser = optparse.OptionParser()
    parser.add_option('--kanjidic', dest='kanjidic')
    parser.add_option('--edict', dest='edict')
    parser.add_option('--enamdict', dest='enamdict')
    parser.add_option('--db', dest='db')

    options, args = parser.parse_args()

    if len(args) == 0 and options.db is not None:
        build_db_sqlite(options.db, options.kanjidic, options.edict, options.enamdict)
    elif len(args) == 1 and options.db is None:
        build_db_json(args[0], options.kanjidic, options.edict, options.enamdict)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
