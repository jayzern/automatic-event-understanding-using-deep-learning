#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import subprocess as sb

inlist="/users/yuvalm/data/rw-eng-with-raw-sentences-and-heads-but-no-malt/exp4/description.txt.files.fixed"
start = 0
end = sys.maxint

if __name__ == '__main__':
    args = sys.argv
    if len(args) > 1:
        start = int(args[1])
    if len(args) > 2:
        end = int(args[2])

    print "processing from file # %d to %d, incl." % (start,end)
    for i,line in enumerate(open(inlist, "r")): #sys.stdin:
        infilename = line.strip()
        if start <= i <= end:
            print "Processing UKWAC file %d: %s ..." % (i,infilename)
            cmd = "/data/semfit/ukwac_converter-2-sesame+anim.py -f %s -o /data/semfit/ukwac-proc-out-2-sesame+anim/ -c" % infilename
            try:
                sb.check_call([cmd], shell=True)
            except sb.CalledProcessError:
                print("ERROR: calling ukwac batch tagger binary with %s" % cmd)
                sys.exit()

#./ukwac_converter.py -f headeval/evaldeps200-attempt-2.xml  -o headeval/try/ 
