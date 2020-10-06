#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import spacy

if __name__ == '__main__':
    from spacy.tokenizer import Tokenizer
    from spacy.lang.en import English
    nlp = spacy.load('en_core_web_sm')
#    nlp = English()
#    print nlp.pipe_names # for debug
    # Create a blank Tokenizer with just the English vocab
    basicEngTokenizer = Tokenizer(nlp.vocab)
    nlp.tokenizer = basicEngTokenizer
    
    for line in sys.stdin:
        doc = nlp(unicode(line.strip()))
        for token in doc:
            print " ".join( (str(token.i), token.text, token.lemma_, token.pos_, token.tag_, token.dep_, str(token.head.i), token.head.text, token.ent_type_, token.ent_iob_))
        print
        
