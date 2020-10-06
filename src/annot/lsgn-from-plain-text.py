#!/usr/bin/env python2
# -*- coding: utf-8 -*-


import json
import sys, os,  traceback
import gzip
import subprocess as sb
from tempfile import *
from socket import gethostname
from itertools import izip, count

__author__ = "Yuval Marton, loosely based on work by p.shkadzko@gmail.com"


def jsonify(sentences):
    output = []
    for sent in sentences:
        resultdict = {}
        resultdict["doc_key"] = "eval"
        resultdict["srl"] = [[],[]]
        resultdict["sentences"] = [sent.split()]

        output.append(json.dumps(resultdict))
    return output

def dejsonify(item):        
    sentence = json.loads(item)
    full_srl = []
    if len(sentence["predicted_srl"]) == 0:
        return "NOTHING_FOUND"

    try:
        for item in sentence["predicted_srl"]:
            predicate = sentence["sentences"][0][item[0]]
            span = sentence["sentences"][0][item[1]:(item[2]+1)]
            full_srl.append([(str(x) + '\t') for x in item] + [str(predicate) + '\t'] + [(str(x) + ' ') for x in span])

        return '/$$/'.join([''.join(x) for x in full_srl]) + '\n'
    except TypeError:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, file=sys.stdout)
        exit(0)
#            return "ERROR ERROR ERROR in dejsonifier" + '\n'
#print(json.dumps(sentence))

def gzip_reader(fname):
        """
        Read a .gz archive and return its contents as a string.
        If the file specified is not an archive it attempt to read it
        as a general file.
        Args:
            *fname* (str) -- file path
        Returns:
            *fdata* (str) -- file contents
        """
        try:
            with gzip.open(fname, 'r') as f:
                fdata = f.read()
        except (OSError, IOError):
            with open(fname, 'r') as f:
                fdata = f.read()
        # return clean_bad_chars(fdata)
        return fdata

def _shell_call(bin, params, input_file, output_file, useStdin) : #,  crashed):
        """
        Call tagger binary from its dir.
        Args:
            | *out_dir* (str) -- output directory path
            | *input_file* (str) -- input file name
            | *output_file* (str) -- output file name
            | *crashed* (int) -- number of tagger crashes if any
        """
        curpath = os.getcwd()

        input_file_path  = input_file  if input_file[0]  == '/' else os.path.join(curpath, input_file) 
        output_file_path = output_file if output_file[0] == '/' else os.path.join(curpath, output_file)
        call = ' '.join([bin, params,
                         ' < ' if useStdin else '', input_file_path,
                         ' > ' if useStdin else '', output_file_path])
        print 'running %s ...' % bin
        try:
            sb.check_call([call], shell=True)
        except sb.CalledProcessError:
            print("ERROR: calling binary, please see "
                  "\"_shell_call()\" method")
            sys.exit()
            

if __name__ == '__main__':
    fn_in = sys.argv[1]
    fn_out= sys.argv[2]
    #print "in: %s, out: %s" % (fin,fout)
    has_header = True
    useStdin = False

    mydir=os.path.dirname(os.path.realpath(__file__))
    lines_txt = gzip_reader(fn_in).split('\n')
    lines_txt = [line for line in (lines_txt[1:] if has_header else lines_txt) if (line.strip() != "" and line[0] != '#') ] 
    lines_jsn = jsonify(lines_txt)    #'\n'.join(jsonify(lines_txt))
    #lines_jsn.insert(0, "sentence")
    print "TXT: %s" % lines_txt[1]
    print "JSN: %s" % lines_jsn[1]
    print 'sentences extracted:', len(lines_txt)
    tmpdir = mkdtemp()
    tfn_in_jsn  = os.path.join(tmpdir, os.path.basename(fn_in) + ".jsn.tmp")
    tfn_out_jsn = os.path.join(tmpdir, os.path.basename(fn_out) + ".jsn.tmp")
    try:
        with open(tfn_in_jsn, 'w') as f:
            f.write('\n'.join(lines_jsn))
    except Exception as ex:
        print('EXCEPTION on {0}: {1}\n{2}'.format(gethostname(), tfn_in_jsn, ex))
        exit()

    print 'tagger READS:', tfn_in_jsn
    print 'tagger WRITES:', tfn_out_jsn
    print 'tmp dir:', tmpdir
        
    _shell_call(os.path.join(mydir, '../RW-relabel/go.sh'), "", tfn_in_jsn, tfn_out_jsn, useStdin) #,  crashed)

    print "Tagger is done."
    try:
        with open(tfn_out_jsn, 'r') as tmpf:
            out_jsn = tmpf.readlines()
    except Exception as ex:
        print('EXCEPTION on{0}: {1}\n{2}'.format(gethostname(), tfn_out_jsn,  ex))
        exit()

    out_txt =  [dejsonify(item) for item in out_jsn]
    print "dejsonify is done."
    
    try:
        with open(fn_out, 'w') as f:
            f.write('\n'.join(out_txt))
    except Exception as ex:
        print('EXCEPTION on {0}: {1}\n{2}'.format(gethostname(), fn_out, ex))
        exit()  
    print "output in %s" % fn_out

    fn_out2 = fn_out+".xml"
    try:
        with open(fn_out2, 'w') as f:
            f.write('\n'.join([ "[ %d ] %s\n%s" % (out_txt2[2], out_txt2[0], out_txt2[1].replace('/$$/','\n')) for out_txt2 in izip( lines_txt, out_txt, count()) ]))
    except Exception as ex:
        print('EXCEPTION on {0}: {1}\n{2}'.format(gethostname(), fn_out2, ex))
        exit()  
    print "output2 in %s" % fn_out2
    
    
    
"""



    taggers.append( TAGGER('he_srl',
            #'/home/ymarton/src/sem-fit/RW-relabel/go.sh',
            os.path.join(mydir, '../RW-relabel/go.sh'),
            #'docker exec semfit1 /root/home/src/sem-fit/RW-relabel/go.sh',
            tagger_params='',
            preproc=lambda sents: '\n'.join(jsonify(sents)), 
            postproc=lambda toklines: [dejsonify(item) for item in toklines],
            unpackInXml = lambda sent: sent.replace('/$$/','\n'),
            useStdin=False,
            isqsub=args.qsub))
"""
