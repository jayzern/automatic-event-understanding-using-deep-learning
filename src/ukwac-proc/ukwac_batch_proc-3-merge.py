#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys, os
import subprocess as sb
from os.path import isfile, join

#inlist="/users/yuvalm/data/rw-eng-with-raw-sentences-and-heads-but-no-malt/exp4/description.txt.files.fixed"
inlist="/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/"
outdir="/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-merged/"
start = 0
end = sys.maxint
mydir = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    args = sys.argv
    if len(args) > 1:
        start = int(args[1])
    if len(args) > 2:
        end = int(args[2])

    print "Merging from file # %d to %d, incl." % (start,end)
    for i,line in enumerate( open(inlist, "r") if os.path.isfile(inlist) else \
                             [join(inlist, f) for f in sorted(os.listdir(inlist)) if isfile(join(inlist, f))] \
#                             [join(inlist, f) for f in os.listdir(inlist) if isfile(join(inlist, f))] \
                           ):
        if start <= i <= end:
            infilename = line.strip()
            logfn = "%s/%s.log.gz" % (outdir, os.path.basename(infilename.strip('.gz')))
            print "Merging UKWAC file %d: %s ..." % (i,infilename)
            cmd = "python %s/ukwac_converter-merger.py -f %s  -o %s  -c" % (mydir, infilename, outdir) \
                  + ' -t \'[' \
                  + '["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/",["rawsent","predicate"]],' \
                  + '["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-malt-but-no-heads/",["malt"]],' \
                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-spacy/",["spacy"]],' \
                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-mrft/",["pre-tokenized","morfette","he_srl"]]]\'' \
                  + " | gzip -9 > %s" % logfn
#                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-mrft/",["morfette"]],' \
#                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223/rw-output/",["he_srl"]]]\'' \
            try:
                sb.check_call([cmd], shell=True)
            except sb.CalledProcessError:
                print("ERROR: calling ukwac batch merger with %s" % cmd)
                sys.exit()
            print "Done merging UKWAC file %d: %s \n   log under %s" % (i,infilename, logfn)


# python ~/src/sem-fit/ukwac-proc/ukwac_converter-merger.py -f /home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/heads.ukwac.fixed-nowiki.node0000.converted.xml.gz  -t '[["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/",["rawsent","predicate"]],["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-malt-but-no-heads/",["malt"]],["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-spacy/",["spacy"]],["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-mrft/",["morfette"]],["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223/rw-output/",["he_srl"]]]' -o  /home/ymarton/data/rw-eng/ukwac-proc-out-20190223-merged/

# for running a list of individual (non long range) files:
# for i in {301..304} 307 308 311 {328..333} 338 340 341 349 352 353 358 366 374 251 253 261 265 267 {279..285}; do ~/src/sem-fit/ukwac-proc/ukwac_batch_proc-3-merge.py $i $i; done
