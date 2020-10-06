#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys,os
import subprocess as sb
from os.path import isfile, join

infilename="/home/ymarton/src/sem-fit/ukwac-proc/headeval/test.xml"
outdir    ="/home/ymarton/src/sem-fit/ukwac-proc/headeval/"
start = 0
end = sys.maxint
mydir = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
#    args = sys.argv
#    if len(args) > 1:
#        start = int(args[1])

    print "processing test file %s" % infilename
    logfn = "%s/%s.log.gz" % (outdir, os.path.basename(infilename.strip('.gz')))
    for cmd in (
            "%s/ukwac_converter.py -f %s -o %s -c" % (mydir, infilename, outdir+"mrft"), # currently he_srl + morfette
            "%s/ukwac_converter-spacy.py -f %s -o %s -c" % (mydir, infilename, outdir+"spacy"),
            "python %s/ukwac_converter-merger.py -f %s  -o %s  -c" % (mydir, infilename, outdir+"merged") \
                  + ' -t \'[' \
                  + '["%s/",["rawsent","predicate"]],' % os.path.dirname(os.path.abspath(infilename)) \
                  + '["%s/",["malt"]],'                % os.path.dirname(os.path.abspath(infilename)) \
                  + '["%s/",["spacy"]],' % (outdir+"spacy")  \
                  + '["%s/",["pre-tokenized","morfette","he_srl"]]]\'' % (outdir+"mrft") \
                  + " | gzip -9 > %s" % logfn
    ):
        print cmd
        try:
            sb.check_call([cmd], shell=True)
        except sb.CalledProcessError:
            print("ERROR: calling ukwac batch tagger binary with %s" % cmd)
            sys.exit()
            
    print "Done merging UKWAC file %s \n   log under %s" % (infilename, logfn)
