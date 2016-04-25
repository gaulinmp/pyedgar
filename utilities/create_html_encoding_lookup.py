import pandas as pd


with open('html_entity_lookups.tsv', 'r') as fh:
    df_lk = pd.read_csv(fh, sep='\t')
    for c in 'string decode unidecode'.split():
        df_lk[c] = df_lk[c].apply(lambda x: x[1:-1] if len(x) > 1 else x)
    df_lk['selected'] = df_lk.apply(lambda x: x.decode if x.lookup == 1 else x.unidecode, axis=1)

    with open('../pyedgar/utilities/_html_encoding_lookup.py', 'w') as fh:
        fh.write("""#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

html_ent_re = re.compile('&[^; ]{1,10};')

def html_ent_re_sub_lambda(re_match):
    ent = re_match.group(0)

    if ent in HTML_ENCODE_LOOKUP:
        return HTML_ENCODE_LOOKUP[ent]
    return HTML_ENCODE_LOOKUP.get(ent.lower(), ent)

def html_ent_re_sub(text):
    return html_ent_re.sub(html_ent_re_sub_lambda, text)

HTML_ENCODE_LOOKUP = {
""")
        existing_strings = list(df_lk.string)
        for i,row in df_lk.iterrows():
            fh.write('"{0}":{1!r},\n'.format(row.string, row.selected))
            if row.string.lower() not in existing_strings:
                fh.write('"{0}":{1!r},\n'.format(row.string.lower(), row.selected))
                existing_strings.append(row.string.lower())

        fh.write("}\n")
