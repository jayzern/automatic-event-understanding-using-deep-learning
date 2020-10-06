#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
from nltk.corpus import wordnet as wn
from nltk.wsd import lesk

def taggit(token, tokens) :
    tokSynset = lesk(tokens, token);
    animSenti = \
        "None" if (tokSynset is None) else \
        "Sentient" if (person in tokSynset._shortest_hypernym_paths(person)) else   \
        "Animate"  if (animate in tokSynset._shortest_hypernym_paths(animate)) else \
        "None"
    return "%s %s" % (str(tokSynset).replace("Synset('","").replace("')",""), animSenti)
  
if __name__ == '__main__':
    person = wn.synset('person.n.01')
    animate= wn.synset('animate_being.n.01')
    #print person, animate
   
    for line in sys.stdin:
        #line = line.replace('/','\\')
        sent = unicode(line.strip())
        tokens = sent.split()
        print "\n".join("%s %s" % (token, taggit(token,tokens)) for token in tokens)
        print

