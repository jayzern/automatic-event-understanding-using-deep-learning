#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import spacy

if __name__ == '__main__':
    nlp = spacy.load('en_core_web_sm')
    for line in sys.stdin:
        #line = line.replace('/','\\')
        doc = nlp(unicode(line.strip()))
        for token in doc:
            print " ".join( (str(token.i), token.text, token.lemma_, token.pos_, token.tag_, token.dep_, str(token.head.i), token.head.text, token.ent_type_, token.ent_iob_))
        print
        
