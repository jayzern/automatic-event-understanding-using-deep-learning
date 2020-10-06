#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys,os
import subprocess as sb
from os.path import isfile, join
import datetime, time

#inlist="/users/yuvalm/data/rw-eng-with-raw-sentences-and-heads-but-no-malt/exp4/description.txt.files.fixed"
#inlist="/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-malt-but-no-heads/"
inlist="/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/"
#outdir=/data/semfit/ukwac-proc-out/ 
outdir="/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-lsgn/"
#outdir="/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-lsgnpy3/"
start = 0
end = sys.maxint
mydir = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    args = sys.argv
    if len(args) > 1:
        subnames = args[1].split(',')
        if len(subnames) <= 1:
           start = int(args[1])
           infilenames = open(inlist, "r") if os.path.isfile(inlist) else \
                             [join(inlist, f) for f in sorted(os.listdir(inlist)) if isfile(join(inlist, f))]
        else:
            start = 0
            infilenames = []
            for subname in subnames:
                infilenames.extend (
                    [join(inlist, f) for f in sorted(os.listdir(inlist)) if (isfile(join(inlist, f)) and (subname in f))]
                )
#            print (infilenames)

    if len(args) > 2:
        end = int(args[2])
        print "processing from file # %d to %d, incl." % (start,end)
        infilenames = infilenames[start:end+1]
    else:
        print "processing files %s.\nLong list:\n%s\n" % (subnames, '\n'.join(infilenames))


    for i,line in enumerate( infilenames ):
            infilename = line.strip()
            print "Processing UKWAC file %d: %s ..." % (start+i, infilename)
            started = datetime.datetime.now()
            # make sure converter only has He++ enabled!
#            cmd = "%s/ukwac_converter.py -f %s -o %s -c" % (mydir, infilename, outdir) # currently he_srl + morfette
            cmd = "%s/ukwac_converter-lsgn.py -f %s -o %s -c" % (mydir, infilename, outdir)
            try:
                sb.check_call([cmd], shell=True)
            except sb.CalledProcessError:
                print("ERROR: calling ukwac batch tagger binary with %s" % cmd)
                sys.exit()
            finished = datetime.datetime.now()
            print ("Started  %s\nFinished %s\nTook %s" % (str(started), str(finished), str(finished-started)))

#./ukwac_converter.py -f headeval/evaldeps200-attempt-2.xml  -o headeval/try/ 
