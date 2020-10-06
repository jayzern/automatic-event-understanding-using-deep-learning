#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# expected input example:
# 7 from from ADP IN prep 6 late  O
# 8 JFK jfk PROPN NNP pobj 7 from PERSON B

import sys
import spacy

COL_SUR = 1
COL_LEM = 2
COL_CPOS = 3
COL_NER = 8
COL_BIO = 9

PLACEHOLDER = ".."
DELIM_PARTS = '|'
DELIM_MWE = '_'
POS_NONE = '?'

tok = ""
lem = ""
pos = ""
ner = ""
verbtok = ""
verblem = ""
tok_stack = []

def print_stack(): 
    global tok_stack
    print "\t".join(tok for tok in tok_stack)
    tok_stack = []
    return

def append_stack(tok, lem, pos, ner):
    global tok_stack
    for i in range(len(tok.split(DELIM_MWE))-1):
        tok_stack.append( DELIM_PARTS.join( [PLACEHOLDER, PLACEHOLDER, POS_NONE, "", ] ))
    tok_stack.append( DELIM_PARTS.join([tok,lem,pos,ner]))
        
if __name__ == '__main__':
    tok_stack = []
    inNounTok = False
    inVerbTok = False
    for line in sys.stdin:
        line = unicode(line.strip().replace('/','\\').replace('|','\\'))
        flds = line.split(' ')
        if len(flds) <= 1:
            if inNounTok or inVerbTok:
                append_stack(tok, tok.lower(), pos, ner)
            print_stack()
            inNounTok = False
            inVerbTok = False
        elif len(flds) == 10:
            if flds[COL_BIO] == "B" :
                if inNounTok:
                    # handle prev noun tok
                    append_stack(tok,lem,pos,ner)
                if inVerbTok:
                    # print previous verb:
                    append_stack( verbtok, verblem, "VERB", "")
                    inVerbTok = False
                inNounTok = True

                tok = flds[COL_SUR]
                ner = flds[COL_NER]
                lem =  flds[COL_LEM]
                pos = "NOUN"
            elif flds[COL_BIO] == "O":
                if inNounTok:
                    # handle prev noun tok
                    append_stack( tok, lem, pos, ner)
                    tok = ""
                else:
                    pass # normal state of things
                inNounTok = False
                if  flds[COL_CPOS] == "VERB":
                    if inVerbTok:
                        # print previous verb:
                        append_stack(verbtok, verblem, "VERB", "")
                    verbtok = flds[COL_SUR]
                    verblem = flds[COL_LEM]
                    inVerbTok = True
                elif flds[COL_CPOS] == "PART" and inVerbTok:
                    # and flds[COL_LEM] not in ("to", "'","'s") and what to do with "look-out posts", ...: # can also check dep head
                    if inVerbTok:
                        verbtok  += DELIM_MWE + flds[COL_SUR]
                        verblem  += DELIM_MWE + flds[COL_LEM]
                    else:
                        raise Exception("Got PART without prior VERB in line '%s'" % line)
                else:
                    if inVerbTok:
                        append_stack(verbtok, verblem, "VERB", "")
                    verbtok = ""
                    inVerbTok = False

                    if flds[COL_CPOS] in ("NOUN","VERB"):
                        pos = flds[COL_CPOS]
                    else:
                        pos = POS_NONE                          
                    append_stack(flds[COL_SUR], flds[COL_LEM], flds[COL_CPOS], flds[COL_NER])
            elif flds[COL_BIO] == "I" :
                if inVerbTok:
                    raise Exception("In NER while in verb tok in line '%s'" % line)
                if not inNounTok:
                    raise Exception("In NER without prior B in line '%s'" % line)
                tok += DELIM_MWE + flds[COL_SUR]
                lem += DELIM_MWE + flds[COL_LEM]
        else:
            if inNounTok or inVerbTok:
                print_stack()
            raise Exception("Problem with input on line '%s' with %d parts" % (line, len(flds)))

    print_stack()
