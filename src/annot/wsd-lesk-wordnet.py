#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
#import nltk
from nltk.wsd import lesk

if __name__ == '__main__':
    #lesk('John loves Mary'.split(), 'loves', synsets=[])
    #lesk('John loves Mary'.split(), 'loves')
    for line in sys.stdin:
        #line = line.replace('/','\\')
        sent = unicode(line.strip())
        tokens = sent.split()
        #for token in tokens:
        print " ".join( str(lesk(tokens, token)) for token in tokens).replace("Synset('","").replace("')","")

        
