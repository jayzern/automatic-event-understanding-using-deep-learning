#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys, os
import subprocess as sb
from os.path import isfile, join
import datetime, time

#inlist="/users/yuvalm/data/rw-eng-with-raw-sentences-and-heads-but-no-malt/exp4/description.txt.files.fixed"
inlist="/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/"
#old_merge_dir="/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-merged/"
#senti_with_prev_merge_dir = "/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20200229-senti/"
outdir="/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20200602-merged/"
start = 0
end = sys.maxint
mydir = os.path.dirname(os.path.abspath(__file__))

if __name__ == '__main__':
    subnames = []
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
        print "Merging from file # %d to %d, incl." % (start,end)
        infilenames = infilenames[start:end+1]
    else:
#        infilenames = open(senti_with_prev_merge_dir, "r") if os.path.isfile(senti_with_prev_merge_dir) else \
#                          [join(senti_with_prev_merge_dir, f) for f in sorted(os.listdir(senti_with_prev_merge_dir)) if isfile(join(senti_with_prev_merge_dir, f))]
#        infilenames = [f.replace(senti_with_prev_merge_dir,inlist)
#                       .replace("converted.xml.converted.xml","converted.xml")
#                       for f in infilenames]
        if subnames:
            print "Merging files %s.\nLong list:\n%s\n" % (subnames, '\n'.join(infilenames))
        else:
            print "Merging files. Long list:\n%s\n" % ('\n'.join(infilenames))

    for i,line in enumerate( infilenames ):
            infilename = line.strip()
            print "Merging UKWAC file %d: %s ..." % (start+i, infilename)
            started = datetime.datetime.now()
            
            logfn = "%s/%s.log.gz" % (outdir, os.path.basename(infilename.strip('.gz')))
            print "Merging UKWAC file %d: %s ..." % (i,infilename)
            cmd = "python %s/ukwac_converter-merger.py -f %s  -o %s  -c" % (mydir, infilename, outdir) \
                  + ' -t \'[' \
                  + '["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/",["rawsent","predicate"]],' \
                  + '["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-malt-but-no-heads/",["malt","lemsent"]],' \
                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-spacy/",["spacy"]],' \
                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-mrft/",["pre-tokenized","morfette"]],' \
                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-lsgn-tok2/",["he_srl"]]]\'' \
                  + " | gzip -9 > %s" % logfn
#                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-mrft/",["morfette"]],' \
#                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223/rw-output/",["he_srl"]]]\'' \
#                  + '["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-lsgnpy3/",["he_srl"]]]\'' \


            try:
                sb.check_call([cmd], shell=True)
            except sb.CalledProcessError as e:
                print("ERROR: calling ukwac batch merger with %s" % cmd)
                exit("ERROR: calling ukwac batch merger with %s\n resulted in %s" % (cmd,e)) # error
            finished = datetime.datetime.now()
            print ("Started  %s\nFinished %s\nTook %s" % (str(started), str(finished), str(finished-started)))       
            print "Done merging UKWAC file %d: %s \n   log under %s" % (i,infilename, logfn)


# python ~/src/sem-fit/ukwac-proc/ukwac_converter-merger.py -f /home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/heads.ukwac.fixed-nowiki.node0000.converted.xml.gz  -t '[["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/",["rawsent","predicate"]],["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-malt-but-no-heads/",["malt"]],["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-spacy/",["spacy"]],["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-mrft/",["morfette"]],["/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223/rw-output/",["he_srl"]]]' -o  /home/ymarton/data/rw-eng/ukwac-proc-out-20190223-merged/

# for running a list of individual (non long range) files:
# for i in {217..218} 435 651 868  1085 1302 1519 1736 \
#                1953 2170 2387 2604   2821 3038 3255 3472 \ 
#                 218  436  652  869   1086 1303 1520 1737 \
#                1954 2171 2388 2605   2822 3039 3256 3473 \
# ; do ~/src/sem-fit/ukwac-proc/ukwac_batch_proc-4-merge-senti-anim.py $i $i; done
#
# python  ~/src/sem-fit/ukwac-proc/ukwac_batch_proc-4b-merge-senti-anim.py 'node0000,node0100,node0200,node0300,node0401,node0501,node0601,node0701,node0801,node0902,node1002,node1102,node1202,node1302,node1402,node1502,node1602,node1702,node1803,node1904,node2004,node2104,node2204,node2305,node2405,node2505,node2606,node2706,node2806,node2906,node3006,node3106,node3206,node3306,node3406'
