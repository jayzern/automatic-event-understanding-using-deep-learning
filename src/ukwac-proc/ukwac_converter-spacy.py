#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
This script uses ukwac corpus as input for various taggers (POS taggers, parers, lemmatizer, SRL, etc.)
sentences are processed and collected in order. 
The result is written as xml file.
The script consists of two classes and several functions that work with these
classes. 
Here is a brief description of the conversion procedure.
Conversion procedure:
    1. Read ukwac file contents.
    2. Normalize contents by removing non-utf8 symbols.
    3. Extract the sentences, 
    4. Expand various contractions like "I'm, you're, let's".
    5. Write extracted ukwac sentences into an input file.
    6. Feed the input file to each tagger
    7. Collect their outputs, and input-sentence-align them.
    8. Create xml representation and write it to disk.
    9. Clean up temp input, output files.
Performance:
    Depending on the taggers you use (see __main__ below)
"""

import argparse
import os
import sys
import re
import gzip
import subprocess as sb
import xml.etree.ElementTree as et
import xml.dom.minidom as mdom
import shutil

from socket import gethostname
from itertools import izip
from collections import deque, defaultdict, OrderedDict as od

from itertools import groupby

from tempfile import *

__author__ = "Yuval Marton, based on work by p.shkadzko@gmail.com"


### uncomment below to generate script execution .png graph
# from pycallgraph import PyCallGraph
# from pycallgraph.output import GraphvizOutput


def detect_missing_files(scan_dir):
    """For unknown reasons ukwac_converter.py might not process all ~3500 ukwac
    files. If this happens, use this function to scan for missed files.
    It prints sge engine commands that you can separately run to reprocess
    each missed file."""
    proc = sb.Popen(['ls', 'parallelized_5000_nowiki'], stdout=sb.PIPE)
    ukwac= set([f.split('.')[2][4:] for f in proc.stdout.read().split()])
    proc = sb.Popen(['ls', scan_dir], stdout=sb.PIPE)
    conv = set([f.split('.')[2][4:] for f in proc.stdout.read().split()])
    missed = ukwac - conv
    # printing the commands to process the missing files
    for m in missed:
        print('qsub -cwd -V -t 1-1:1 -b y ./ukwac_converter.py -qs -f parallelized_5000_nowiki/ukwac.fixed-nowiki.node%04d.gz' % int(m))


class UkwacTools:
    """
    Class that represents a collection of static methods required to parse
    ukWaC corpus.
    <Class implementation in order to wrap a mess of various string processing
    functions into a single class>
    """
    @staticmethod
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

    @staticmethod
    def clean_bad_chars_with_iconv(fname, data):
        """
        Use iconv to trim all bad utf-8 chars from the file.
        <I didn't notice if this method helps to get rid
        of SENNA's skipped chars warning. Just leave it here as an example
        of possible solution to remove non-utf8 chars using shell utils.>
        Args:
            *fname* (str) -- file path
            *data* (str) -- file contents
        Returns:
            *cleaned_data* (str) -- file contents with non-utf8 chars removed
             using "iconv" tool.
        """
        with open(fname + '_temp', 'w') as f:
            f.write(data)
        sb.call('iconv -f utf-8 -t utf-8 -c %s > %s'
                % (fname + '_temp', fname + '_clean'), shell=True)
        with open(fname + '_clean', 'r') as f:
            cleaned_data = f.read()
        os.remove(fname + '_temp')
        os.remove(fname + '_clean')
        return cleaned_data

    @staticmethod
    def reduce_contr(data):
        """
        Apply a dictionary of common contractions.
        SENNA is not able to tokenize and assign a correct POS-tag to a
        contracted token. Applying contractions allows us to improve SENNA's
        output.
        Args:
            *data* (str) -- preprocessed text string
            
        Returns:
            *ndata* (str) -- preprocessed text string
        """
        cntr = get_contractions()
        reps = dict((re.escape(k), v) for k, v in cntr.iteritems())
        
        rpatt = re.compile("|".join(reps.keys()))
        ndata = rpatt.sub(lambda m: reps[re.escape(m.group(0))], data)

        
#        tok_regex = get_tok_regex() # yuval
#        tok_regex =  dict((re.escape(k), v) for k, v in get_tok_regex().iteritems()) # get_tok_regex() # yuval
#        tok_regex =  dict((k, v) for k, v in get_tok_regex().iteritems())  # yuval
#        reps.update(tok_regex)
        for k,v in get_tok_regex(): #.iteritems():
            ndata = re.sub(k, v, ndata)
        #ndata = re.sub(r'([a-zA-Z])([\-\/:])', r'\1 \2', ndata) # Yuval added
        #ndata = re.sub(r'([\-\/:])([a-zA-Z])', r'\1 \2', ndata)
        
        return ndata

    @staticmethod
    def index_text_ids(cleaned_data):
        """
        Collect text ids and calculate sentences within <text id> </text> tags
        in order to insert ids during xml building.
        Args:
            *cleaned_data* (str) -- file contents with non-utf8 chars removed
        Returns:
            *ids_index* (dict) -- an ordered dict of url string and a number of
             sentences
        """
        rtext_id = re.compile(r'<text id="(.*)">')
        ids = rtext_id.findall(cleaned_data)
        if not ids: return None
        ids_index = od()
        n = 0
        for segment in cleaned_data.split('<text id='):
            if not segment: continue
            ids_index[ids[n]] = len(segment.split('<s>')) - 1
            n += 1
        return ids_index

    @staticmethod
    def include_malt(data_lines):
        """
        Extract parent-child information from source file that was generated
        by malt parser.
        Args:
            *data_lines* (list) -- a list file sentences
        Returns:
            *malt_dic* (dict) -- a dict of sent number and its malt parse
        """
        malt_dic = defaultdict(str)
        sent = 0
        goodline = re.compile(r'.+ .+ [0-9]+ [0-9]+ [A-Z]+')
        for line in data_lines:
            if line == '<s> <S>':
                sent += 1
                malt_dic[sent] = '\n'
            elif line == '</s> <S>':
                continue
            elif not len(line.split()) >= 5:  # malt data is messy
                continue
            else:
                l = line.split()[1:6]
                l.append('\n')
                nline = ' '.join(l)
                if goodline.match(nline):
                    malt_dic[sent] += nline
        return malt_dic

    @staticmethod
    def clean_bad_chars(mess):
        """
        Remove some ukwac specific and non-utf8 chars from the file otherwise
        SENNA will generate skipped char warnings and it's parsing quality will
        degrade.
        Args:
            *mess* (str) -- file contents
        Returns:
            *nice* (str) -- file contents with bad chars removed
        """
        mess0 = re.sub(r'', '\'', mess)  # replace ""
        mess1 = re.sub(r'[^\x00-\x7F]+', '', mess0)  # remove non utf8 chars
        mess2 = re.sub(r'&', '&amp;', mess1)
        # hardcore removal, maybe this alone is enough
        bad_chars = '\x81\x8d\x8f\x90\x9d\x01\x03\x0b\x17\x1a\x1c\x1d\x05' \
                    '\x06\x07\x10\x11\x12\x13\x14\x15\x16\x18\x1a\x19\x1e' \
                    '\x1f\x04\x02\x08\x0c\x0e\x0f\x1b'
        nice = mess2.translate(None, bad_chars)
        return nice

    @staticmethod
    def insert_sent_delims(sents):
        """
        Insert sentence delimiters.
        SENNA is quite sensitive to input which is not properly separated.
        In order to process each sentence correctly we insert "``" delimiters.
        Args:
            *sents* (str) -- sentences extracted from ukwac corpus
        Returns:
            *sentences separated with "\`\`"*
        """
        sep_sents = tuple(''.join([s, '\r\n``\r\n'])
                          for s in sents.split('\n') if s)
        return ''.join(sep_sents)

    @staticmethod
    def gzip_xml(fname):
        """
        Read and compress specified file, remove original file.
        Args:
            *fname* (str) -- file name
        """
        with open(fname, 'r') as f:
            fdata = f.read()
        with gzip.open(fname + '.gz', 'w') as gf:
            gf.write(fdata)
            os.remove(fname)
        print fname + '.gz successfully archived'

    @staticmethod
    def merge_POS(sent):
        """
        This function merges XP and POS into one POS
        Args:
            *sent* (str) -- sentence string
        Returns:
            *stack* (deque) -- deque list of POS$ tags
        """
        stack = deque()
        for w in sent:
            if re.match(r'.*/POS$', w[0]):
                if not stack: continue  # because single quote can tagged POS
                prev_w, prev_tag = stack.pop()
                new_w = ''.join([prev_w.split('/')[0], w[0]])
                w = (new_w, prev_tag)
            stack.append(w)
        return stack

    @staticmethod
    def append_to_xml(fname, root):
        """
        Create xml file header, prettify xml structure and write xml
        representation of the sentences using ``\\r\\n`` as a separator.
        <IMPORTANT! Take into account that output file shall contain sentences
        separated by ``\\r\\n``. Head searching will not work otherwise. This
        is an ugly hack for ``<text id></text>`` tags to contain correct
        sentences.>
        Args:
            | *fname* (str) -- file name to write the data to
            | *root* (xml.etree object) -- xml.etree root object
        """
        rxml_header = re.compile(r'<\?xml version="1.0" \?>')
        ugly = ""
        even_more_nice_xml = "  XML FAILURE  "
        try:
            ugly = et.tostring(root, 'utf-8', method='xml')
            parsed_xml = mdom.parseString(ugly)
            nice_xml = parsed_xml.toprettyxml(indent=" " * 3)
            even_more_nice_xml = rxml_header.sub('', nice_xml)
        except Exception as e:
            print("Error: cannot convert this to XML: '%s'.\n  ugly='%s'.\n  errMeesage=%s.\n" % (root,ugly,e))
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback, file=sys.stdout)
            print("XML dump:")
            try:
                et.dump(root)
            except:
                print("  << et.dump also failed >> \n")
            print
        with open(fname, 'a') as f:
            f.write(even_more_nice_xml)
            f.write('\r\n')  # delimiter required by head_searcher

    @staticmethod
    def get_governors(sent, sent_chunk):
        """
        Retrieve and return a list of governors "S-V" from sentence columns.
        <if a column does not contain a governor an empty tuple is appended>"
        Args:
            | *sent* (str) -- a list of word, POS-tag, word index and role
               tuples:
               ``[('first/JJ/3', ('I-A1',)), ('album/NN/4', ('E-A1',))]``
            | *sent_chunk* (str) -- ukwac tab separated column data
        Returns:
            *govs* (list) -- a list of gov tuples:
             ``[('use/VBD/2',), ('mark/VB/4',)]``
        """
        govs = []
        for i in range(len(sent[0][1])):
            govs.append(tuple([s[0] for s in sent if 'S-V' in s[1][i]]))
        return govs

    @staticmethod
    def get_dependants(sent, idx, sent_chunk):
        """
        Retrieve roles for a given governor.
        Args:
            | *sent* (list) -- a list of word, POS-tag, word index and role
            |  tuples:
                ``[('first/JJ/3', ('I-A1',)), ('album/NN/4', ('E-A1',))]``
            | *sent_chunk* (str) -- ukwac tab separated column data
            | *idx* (int) -- index to access correct ukwac column
        Returns:
            | *role_bag* (list) -- a list of dicts where dep role is key and
               words, POS-tags, word indeces are values:
                ``[{'V': 'justify/VB/20'},
                  {'A1': 'a/DT/21 full/JJ/22 enquiry/NN/23'}]``
        """
        rarg = re.compile(r'(?![O])[A-Z0-9\-]+')
        # in case of bad parsing
        try:
            dep_roles = [(rarg.match(d[1][idx]).group(), d[0]) for d in sent
                         if rarg.match(d[1][idx])]
        except:
            dep_roles = [('', 0)]
        role_bag = []
        role_chunk = ()
        for i in iter(dep_roles):
            if re.match(r'B-', i[0]):
                role_chunk = (i[1],)
                continue
            elif re.match(r'I-', i[0]):
                role_chunk += (i[1],)
                continue
            elif re.match(r'E-', i[0]):
                role_chunk += (i[1],)
                role_bag.append({i[0].lstrip('[CBIE]-'): ' '.join(role_chunk)})
                continue
            else:
                role_bag.append({i[0].lstrip('S-'): i[1]})
                continue
        return role_bag

    @staticmethod
    def add_vps(xml_tree):
        """
        Search for verb phrases, merge verb particles with the verb
        ("make_out") and modify the result output accordingly.
        Args:
            |*xml_tree* (ElementTree root) -- xml representation of a string
        Returns:
            |*xml_tree* (ElementTree root) -- xml representation of a string
             with merged verb phrases.
        """
        def check_match(vp, vpi, tok, toki):
            """Check word and index match."""
            return tok == vp.rsplit('_', 2)[0] and (toki == int(vpi) or
                                                    abs(int(toki)-int(vpi)) <= 2)
        # regex for verb
        rxvb = re.compile(r'([^ ]+) v[a-z]{1,3} ([0-9]+) [0-9]+')
        # regex for particle
        rxpr = re.compile(r'([^ ]+) (rp|in|rb|to) [0-9]+ ([0-9]+) (prt)')
        # regex for verb and particle merge
        rpsub = re.compile(r'([^ ]+) (v[a-z]+)')

        # store found verb phrases
        verb_phrase = od()
        # search for phrasal verbs in malt block
        for xml_elem in xml_tree:
            if xml_elem.tag == 'malt':
                start = 0
                malt_block = xml_elem.text.split('\n')
                for n, line in enumerate(malt_block[start:]):
                    vb_matched = rxvb.match(line)
                    if vb_matched:
                        start = n
                        # accumulate vp particles and preps
                        prlines = []
                        vbline, vb_idx = vb_matched.string, vb_matched.group(2)
                        # save the indeces and matched strings
                        # search for particle
                        for pline in malt_block[start - 1:]:
                            pr_matched = rxpr.match(pline)
                            if pr_matched:
                                prline = pr_matched.string
                                pr, pr_link = pr_matched.group(1), pr_matched.group(3)
                                # check if found particle links to previous verb
                                if pr_link != vb_idx:
                                    continue
                                # merge a particle with a prhasal verb
                                new_vbline = rpsub.sub(r'\1_{0} \2'.format(pr),
                                                       vbline, 1)
                                # merge malt block
                                malt_block[malt_block.index(vbline)] = new_vbline
                                vbline = new_vbline
                                prlines.append(prline)
                        verb_phrase[vbline] = prlines
                # remove non vp keys
                verb_phrase = od((vp, verb_phrase[vp]) for vp in verb_phrase
                                 if verb_phrase[vp])
                xml_elem.text = '\n'.join(malt_block)
            # process SENNA block
            # insert vp into lemsent
            elif xml_elem.tag == 'lemsent':
                lemsent = xml_elem.text
                lemsent_lst = lemsent.split()
                for vp in verb_phrase:
                    vp, vi = vp.split()[0:3:2]
                    for ti, tok in enumerate(lemsent_lst[:], 1):
                        if check_match(vp, vi, tok, ti):
                            lemsent_lst[ti-1] = vp
                            break
                # rejoin the merged vps with the rest of the sentence
                xml_elem.text = ' '.join(lemsent_lst)
            # insert vp into predicates block
            elif xml_elem.tag == 'predicate':
                for vp in verb_phrase:
                    vp, vi = vp.split()[0:3:2]
                    for elem in xml_elem:
                        if elem.tag == 'governor':
                            gov, tag, govi = elem.text.rsplit('/', 2)
                            if check_match(vp, vi, gov, govi):
                                elem.text = '/'.join([vp, tag, govi])
                        elif elem.tag == 'dependencies':
                            for el in elem:
                                el_lst = el.text.split()
                                for dep_tok in el_lst:
                                    dep, tag, depi = dep_tok.rsplit('/', 2)
                                    if check_match(vp, vi, dep, depi):
                                        el_lst[el_lst.index(dep_tok)] = '/'.join([vp, tag, depi])
                                        break
                                el.text = ' '.join(el_lst)
        return xml_tree


class TAGGER:
    """
    Class that runs a line tagger (lemmatizer, oparser, role labeler etc.) 
    and cleans up after itself.
    """
    def __init__(self, name, tagger_bin, tagger_params,
                 preproc=lambda x: x, postproc=lambda x: x, unpackInXml=lambda x: x,
                 useStdin=True, isqsub=False):
        """
        Args:
            | *tagger_bin* (str) -- path to tagger executable
            | *isqsub* (bool) -- if True, use forbin grid engine
        """
        self.runpath = os.getcwd()
        self.tagger_bin = tagger_bin
        self.name = name
        self.tagger_params = tagger_params
        self.preproc = preproc
        self.postproc = postproc
        self.unpackInXml = unpackInXml
        self.useStdin = useStdin
        self.qsub = isqsub
        self.input_files = []
        self.output_files = []

    def _shell_call(self, input_file, output_file, crashed):
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
        call = ' '.join([self.tagger_bin, self.tagger_params,
                         ' < ' if self.useStdin else '', input_file_path,
                         ' > ' if self.useStdin else '', output_file_path])
        print 'running tagger %s ...' % self.tagger_bin
        try:
            sb.check_call([call], shell=True)
        except sb.CalledProcessError:
            print("ERROR: calling tagger binary, please see "
                  "\"tagger._shell_call()\" method")
            sys.exit()

    def run(self, sents, input_fname, output_fname):
        """
        Write extracted sentences into input file, invoke tagger binary and
        keep output file name in a list.
        Args:
            | *out_dir* (str) -- output directory path
            | *sents* (str) -- ukwac extracted sentences, separated with "\`\`"
            | *input_fname* (str) -- input file name
            | *output_fname* (str) -- output file name
        """
        tmpdir = mkdtemp()
        input_fname = os.path.join(tmpdir, input_fname)
        output_fname = os.path.join(tmpdir, output_fname)
        #sents_list = sents.split('\r\n``\r\n')
        #print 'sentences extracted:', len(sents_list) - 1
        print 'sentences extracted:', len(sents)
        print 'tagger READS:', input_fname
        print 'tagger WRITES:', output_fname
        print 'tmp dir:', tmpdir
        try:
            #with open(os.path.join(os.getcwd(), input_fname), 'w') as f:
            with open(input_fname, 'w') as f:
                f.write(self.preproc(sents))
        except Exception as ex:
            print('EXCEPTION on {0}: {1}\n{2}'.format(gethostname(), input_fname, ex))
            exit()
        tmp_output_fname = output_fname + '.tmp'
        self._shell_call(input_fname, tmp_output_fname, 0)

        try:
            #with open(os.path.join(os.getcwd(),  tmp_output_fname), 'r') as tmpf:
            with open(tmp_output_fname, 'r') as tmpf:
                outsents = tmpf.readlines()
        except Exception as ex:
            print('EXCEPTION on{0}: {1}\n{2}'.format(gethostname(), tmp_output_fname,  ex))
            exit()
        #print "outsents"
        #print outsents[:10]
        try:
            #with open(os.path.join(os.getcwd(),  output_fname), 'w') as f:
            with open(output_fname, 'w') as f:
                if len(outsents) > 1:
                    f.write('\n'.join(line.strip() for line in self.postproc(outsents)) )
                else:
                    f.write('\n'.join(self.postproc(outsents[0].strip().split('\n'))) )
        except Exception as ex:
            print('EXCEPTION on {0}: {1}\n{2}'.format(gethostname(), output_fname, ex))
            exit()
        #print "postproc outsents", len(outsents), len( self.postproc(outsents))
        #print self.postproc(outsents)[:10]
        self.output_files.append(output_fname)

    def clean_up(self, out_dir, in_file, out_file, result_fname):
        """
        Remove input and output files after conversion.
        Args:
            | *out_dir* (str) --  output directory path
            | *in_file* (str) -- input file name
            | *out_dir* (str) -- output file name
            | *result_fname* (str) -- final result file name
        """
        if self.qsub:
            try:
                sb.call(['ssh', 'forbin'])
                sb.call(['mv', result_fname+'.gz', out_dir])
            except (IOError, OSError):
                print 'ERROR: could not ssh into forbin'
                print 'ERROR: mv result_fname to $out_dir'
        try:
            for f1, f2 in zip(self.input_files, self.output_files):
                os.remove(f1)
                os.remove(f2)
        except (IOError, OSError):
            print 'Could not remove files:', self.input_files, \
                self.output_files
        try:
            os.remove(in_file)
            os.remove(out_file)
            os.remove(out_file + '.tmp')
        except (IOError, OSError):
            print 'Could not remove files:', in_file, out_file
        self.input_files = []
        self.output_files = []

    def get_output_files(self):
        """Getter for ``self.output_files``"""
        return self.output_files

    def get_input_files(self):
        """Getter for ``self.input_files``"""
        return self.input_files



def extract_ukwac_data(data):
    """
    Extract 2 columns from ukwac files, create an ordered dict of
    ("word", "lemma") pairs and construct sentences for SENNA input.
    Args:
        *data* (str) -- file contents
    Returns:
        | *norm_sents* (str) -- sentences reconstructed from ukwac and
           separated by "\`\`"
        | *dict_lemmas* (dict) -- a dict of all words and their lemmas
        | *text_ids* (OrderedDict) -- an ordered dict of url string and a
           number of sentences, that belong to this url. Used in order to
           provide source reference for extracted sentences
        | *include_malt_data* (dict) -- dict of sentence number and malt parse
           data extracted from ukwac file
    """
    clean_data = UkwacTools.clean_bad_chars(data)
    id_index = UkwacTools.index_text_ids(clean_data)
    """
    rtext = re.compile(r'</?text>?')
    #rlabel = re.compile(r'(</?s>)')
    rlabel = re.compile(r'(</?sentence>)')
    cdata = rtext.sub('', clean_data)
    lcdata = rlabel.sub(r'\1 <S>', cdata)
    lines = [l for l in lcdata.split('\n')]
    chunks = [tuple(l.split()[0:2]) for l in lines if len(l.split()) > 1]
    pairs = tuple(chunks)
    dict_lemmas = dict(pairs)
    sents = ' '.join([w[0] for w in pairs])
    norm_sents = UkwacTools.insert_sent_delims(UkwacTools.reduce_contr(sents))
    """
    rtokens = re.compile(r'<sentence>(.*?)</sentence>')
    sents = rtokens.findall(clean_data)
    sents = UkwacTools.reduce_contr('\t'.join(sents)).split('\t')
    rtext_id = re.compile(r'<text>(.*?)</text>')
    ids = rtext_id.findall(clean_data)
    rfilename = re.compile(r'<filename>(.*?)</filename>')
    orig_filenames = rfilename.findall(clean_data)

    if len(sents) == 0 or sents[0] == "":
        rtokens = re.compile(r'<rawsent>(.*?)</rawsent>')
        sents = rtokens.findall(clean_data)
        sents = UkwacTools.reduce_contr('\t'.join(sents)).split('\t')
    if len(ids) == 0:
#        rtext_id = re.compile(r'(?:<text |<rawsent>)[\s\r\n]*(.*?)(?:/>|</rawsent>)', re.MULTILINE)
        rtext_id = re.compile(r'(<text |<rawsent>)[\s\r\n]*(.*?)[\s\r\n]*(?:/>|</rawsent>)', re.MULTILINE)
        ids_tmp = rtext_id.findall(clean_data)
        ids = []
        last_id = ""
        for i in range(len(ids_tmp)):
 #            if ids_tmp[i][:3] == "id=":   
#                last_id = ids_tmp[i]
            if ids_tmp[i][0] == "<text ":   
                last_id = ids_tmp[i][1]
                #print last_id
                continue #i += 1
            ids.append(last_id)
    if len( orig_filenames) == 0:
        orig_filenames = ids
        
    if len(sents) != len(ids) or len(ids) != len( orig_filenames):
        print "DBG: sents='%s'...\n ids='%s'...\n orig_filenames='%s'..." % (sents[:100], ids[:100], orig_filenames[:100])
        raise Exception("Format problem: %d sents, %d ids, %d orig_filenames" % (len(sents), len(ids), len( orig_filenames)))

    return sents,  orig_filenames, ids


def build_xml(orig_texts, orig_filenames, ids, result_fname, taggers, pverbs):
    """
    Read output file and build its xml representation.
    Args:
        | *lemmas* (dict) -- dict of word -> word lemma: ``{'shops': 'shop'}``
        | *id_idx* (OrderedDict) -- an ordered dict of url string and a number
           of sentences that belong to it
        | *result_fname* (str) -- final result file name
        | *malt_data* (defaultdict) -- Malt parser data extracted from ukwac
           files and converted into a dict
           ``{sent number: parsed sent string}``
        | *pverbs* (bool) -- if True, find and add verb phrases
    """

    orig_texts_iter = iter(orig_texts)
    orig_filenames_iter = iter ( orig_filenames)
    ids_iter = iter(ids)
    subElem = [None,] * len(taggers)
    
    root = et.Element("i_m_groot")
    os.chdir(os.path.dirname(result_fname))  # cd into parent dir
    print "building XML with these taggers: ", [tagger.name for tagger in taggers]
    print [tagger.get_output_files() for tagger in taggers]
    for outfiles in zip(*[tagger.get_output_files() for tagger in taggers]):
        print "processing", outfiles
        fs = [ open(outfile, 'r') for outfile in outfiles]
        sent_views = [f.read().strip().split('\n') for f in fs]

        ## iterating through sentences extracted from OUTPUT_FILE
        sent_cnt = 0
        abs_sent_cnt = 1
        
        for sent_per_tagger in izip(*sent_views):
            sent_node = et.SubElement(root, "s")
            sent_node.set("number", str(sent_cnt))
            sent_node.set("id", next(ids_iter))
            sent_node.set("orig_filename", next(orig_filenames_iter))

            rawsent_text = et.SubElement(sent_node, "pre-tokenized")
            rawsent_text.text  = next(orig_texts_iter) 

            for ti in range(len(sent_per_tagger)):
                subElem[ti] = et.SubElement(sent_node, taggers[ti].name)
                subElem[ti].text = taggers[ti].unpackInXml(sent_per_tagger[ti])                 

            sent_cnt += 1
    # appending formatted xml to the file# appending formatted xml to the file
    UkwacTools.append_to_xml(result_fname, root)
    UkwacTools.gzip_xml(result_fname)


def ukwac_convert(args, taggers):
    """
    Main function.
    Call methods required for ukwac corpus conversion into xml representation.
    Args:
        *args* (dict) -- parsed arguments specified at command line
    """
    # collect and redefine user specified args
    try:
        if args.file:
            files = [args.file]
        else:
            sge_id = '%04d' % (int(os.environ.get('SGE_TASK_ID')) - 1)
            name = os.path.join(args.dir,
                                'ukwac.fixed-nowiki.node' + sge_id + '.gz')
            files = [name]
    except TypeError:
        if not args.file and args.dir:
            files = [os.path.join(args.dir, name)
                     for name in os.listdir(args.dir)]
        elif args.file:
            files = [args.file]
        else:
            print("ERROR: Please provide input dir or input file name.")
            sys.exit()
    try:
        os.mkdir(args.out)
    except OSError:
        print("Output directory already exists! %s" % args.out)

    # Start ukwac conversion
    isqsub = args.qsub
    for filename in files:
        ukwac_fname_path = os.path.join(filename)
        ukwac_fname = '.'.join([os.path.basename(ukwac_fname_path.strip('.gz')),
                                'converted.xml'])
        result_fname = os.path.join(args.out, ukwac_fname) if args.out else os.path.join(os.getcwd(), ukwac_fname)
        print 'reading %s...' % filename
        fdata = UkwacTools.gzip_reader(ukwac_fname_path)
        print 'extracting sentences...'
        #sents, word_lemma, id_index, malt_dic = extract_ukwac_data(fdata)
        sents,  orig_filenames, id_index  = extract_ukwac_data(fdata)
        
        # make sure there are no consecutive identical sentences, because this will mess up output alignment:
        prev_sent = ""
        for i in xrange(1, len(sents)):
            #if i >= len(sents):
            #    break
            if sents[i].lower() == sents[i-1].lower():
                print "WARNING: duplicate input sentence %d: '%s'" % (i, sents[i])
                sents[i] += " ( DUPLICATE %d )" % i

                
        for tagger in taggers:
            #grid_tagger_in = '.'.join([os.path.basename(ukwac_fname.strip('.gz')),
            grid_tagger_in = '.'.join([os.path.join(os.getcwd(), args.out, ukwac_fname.strip('.gz')),
                tagger.name, 'input'])
            #grid_tagger_out = '.'.join([os.path.basename(ukwac_fname.strip('.gz')),
            grid_tagger_out = '.'.join([os.path.join(os.getcwd(), args.out, ukwac_fname.strip('.gz')),
                tagger.name, 'output'])
            out_dir = os.path.join(tagger.runpath, args.out)

            tagger.ifn = grid_tagger_in
            tagger.ofn = grid_tagger_out
            # Prepare remote environment and assign paths for qsub machines
            if isqsub:
                # WARNING: hardcoded stuff
                # will contain temporary files
                forbin_local = '/local/pavels'
                # original tagger dir
                tagger_proj_dir = '/proj/rollenwechsel.shadow/tagger'
                # local tagger dir on qsub machine
                tagger_qsub_dir = '/local/pavels/tagger'
                if not os.path.isdir(forbin_local):
                    os.makedirs(forbin_local)
                if not os.path.isdir(tagger_qsub_dir):
                    # copy complete tagger dir to remote machine if not exist
                    shutil.copytree(tagger_proj_dir, tagger_qsub_dir)
                os.chdir(forbin_local)
                tagger.runpath = forbin_local
            tagger.run(sents, grid_tagger_in, grid_tagger_out)
        print 'creating xml...'
        #build_xml(word_lemma, id_index, result_fname, malt_dic, args.pverbs)
        build_xml(sents,  orig_filenames, id_index, result_fname, taggers, args.pverbs)
        
        if args.cleanup:
            print 'cleaning...'
            for tagger in taggers:
 #               tagger.clean_up(out_dir, grid_tagger_in, grid_tagger_out, result_fname)
                tagger.clean_up(out_dir, tagger.ifn, tagger.ofn, result_fname)
        else:
            print "Left behind temp files in %s, such as " % out_dir, grid_tagger_in, grid_tagger_out, result_fname
        print 'done\n'


def get_contractions():
    """Return special contractions dict."""
    contr = {
             "Are n't": "Are not",
             "are n't": "are not",
#             "Ca n't": "Cannot",
#             "ca n't": "cannot",
             "Ca n't": "Can not",
             "ca n't": "can not",
             "Cannot": "Can not",
             "cannot": "can not",       
             "could 've": "could have",
             "Could n't": "Could not",
             "could n't": "could not",
             "could n't 've": "could not have",
             "Did n't": "Did not",
             "did n't": "did not",
             "Does n't": "Does not",
             "does n't": "does not",
             "Do n't": "Do not",
             "do n't": "do not",
             "Had n't": "Had not",
             "had n't": "had not",
             "had n't 've": "had not have",
             "Has n't": "Has not",
             "has n't": "has not",
             "Have n't": "Have not",
             "have n't": "have not",
             "he'd 've": "he would have",
             "Is n't": "Is not",
             "is n't": "is not",
             "Let 's": "Let us",
             "let 's": "let us",
             "might n't": "might not",
             "might n't 've": "might not have",
             "might 've": "might have",
             "Must n't": "Must not",
             "must n't": "must not",
             "must 've": "must have",
             "need n't": "need not",
             "Sha n't": "Shall not",
             "sha n't": "shall not",
             "Should n't": "Should not",
             "should n't": "should not",
             "should n't 've": "should not have",
             "Should 've": "Should have",
             "should 've": "should have",
             "Was n't": "Was not",
             "was n't": "was not",
             "Were n't": "Were not",
             "were n't": "were not",
             "Wo n't": "Will not",
             "wo n't": "will not",
             "Would n't": "Would not",
             "would n't": "would not",
             "Would 've": "Would have",
             "would 've": "would have",
             "we 'll": "we will",
             "We 'll": "We will",
             "we 've": "we have",
             "We 've": "We have",
             "You 'll": "You will",
             "you 'll": "you shall",
             "You 've": "you have",
             "you 've": "you have",
             "I 've": "I have",
             "i 've": "i have",
             "He 'll": "He will",
             "he 'll": "he will",
             "She 'll": "She will",
             "she 'll": "she will",
             "I 'll": "I shall",
             "i 'll": "i shall",
             "it 'll": "it will",
             "It 'll": "It will",
             "It 's": "It is",
             "it 's": "it is",
             "they 'll": "they will",
             "They 'll": "They will",
             "I 'm": "I am",
             "i 'm": "i am",
             "would n't 've": "would not have",
             "You 're": "You are",
             "you 're": "you are",
             "We 're": "We are",
             "we 're": "we are",
             "They 're": "They are",
             "they 're": "they are",
             "They 've": "They have",
             "they 've": "they have",
#             " '": "'",                # Yuval commented out 20180928
             "<s>": "",
             "</s>": "\n",
             }
    return od(contr)

def get_tok_regex():
    tok_regex = (                                        # more general transformations are at the end
        (r"([a-zA-Z0-9])'s\b" , r"\1 's"),
        (r"(\d\%?)([a-zA-Z]+)\b" , r"\1 \2"),              # number and units

        (r"\b([Dd]id|[Dd]o|[Cc]ould|[Ww]ould|[Ww]as|[Ww]ere) ?n ?'? ?t\b" , r"\1 not"),
        (r"\b[Cc]a ?n ?'? ?t\b", r"can not"),
        (r"\b[Ww]o ?n ?'? ?t\b", r"will not"),

        (r"\b[Ii] ai ?n ?'? ?t\b", r"I am not"),
        (r"\b([Ww]e|[Yy]ou?|ye|[Tt]hey) ai ?n ?'? ?t\b", r"\1 are not"), 
        (r"\b([Hh]e|[Ss]he|[Ii]t|[Tt]here|[Tt]his|[Tt]hat) ai ?n ?'? ?t\b", r"\1 is not"),
#        (r"([^(I|i|We|we|You|you|yo|ye|They|they)]) ai ?n ?'? ?t\b", r"\1 is not"),
#        (r"([^(\bI|\bi|\bWe|\bwe|\bYou|\byou|\byo|\bye|\bThey|\bthey)]) ai ?n ?'? ?t\b", r"\1 is not"),
        (r"\bai ?n ?'? ?t\b", r"is not"),
        
        (r"\b[Ii] ?'? ?m\b", r'I am'),
        (r"\b[Ii] ?'? ?ve\b", r'I have'),
        (r"\b[Ii][ '] ?d\b", r'I would'),                       # leave ID/id/Id as is; ambiguous also between had/would
        (r"\b[Ii][ '] ?ll\b", r'I will'),
        (r"\b([Ww]e)[ '] ?re?\b", r'\1 are'),                   # leave "were" as is
        (r"\b([Ww]e) ?'? ?ve\b", r'\1 have'),
        (r"\b([Ww]e)[ '] ?d\b", r'\1 would'),                       # leave wed as is; ambiguous also between had/ would
        (r"\b([Ww]e)[ '] ?ll\b", r'\1 will'),
        
        (r"\b([Yy]ou) ?'? ?re?\b", r'\1 are'),
        (r"\b([Yy]ou) ?'? ?ve\b" , r'\1 have'),
        (r"\b([Yy]ou) ?'? ?d\b"  , r'\1 would'),                       # leave wed as is; ambiguous also between had/ would
        (r"\b([Yy]ou) ?'? ?ll\b" , r'\1 will'),
        
        (r"\b(He|he|She|she) ?'? ?s\b" , r'\1 is'),                      # ambiguous is/has
        (r"\b(He|he|It|it) ?'? ?d\b"   , r'\1 would'),                   #  ambiguous also between had/ would
        (r"\b(She|she)[ '] ?d\b"       , r'\1 would'),                   # leave shed as is; ambiguous also between had/ would
        (r"\b(He|he|She|she)[ '] ?ll\b", r'\1 will'),                    # leave hell/shell as is; 
        (r"\b(It|it) ?'? ?ll\b"        , r'\1 will'),                    # leave hell/shell as is; 

        (r"\b([Tt]hey) ?'? ?re?\b"     , r'\1 are'),
        (r"\b([Tt]hey) ?'? ?ve\b"      , r'\1 have'), 
        (r"\b([Tt]hey) ?'? ?d\b"       , r'\1 would'),                   # ambiguous also between had/ would
        (r"\b([Tt]hey) ?'? ?ll\b"      , r'\1 will'),
        
        (r"\b([Ww]ho) ?'? ?s\b" , r'\1 is'),                         # ambiguous is/has
        (r"\b([Ww]ho) ?'? ?re?\b", r'\1 are'),                       # ambiguous also betwee "are" and "were" 
        (r"\b([Ww]ho) ?'? ?ve\b", r'\1 have'),
        (r"\b([Ww]ho) ?'? ?d\b", r'\1 would'),                       # ambiguous also between had/ would
        (r"\b([Ww]ho)[ '] ?ll\b", r'\1 will'),

        (r' ?\&( ?amp ?; ?)+', r' & '),                              # HTML espace codes
        (r' ?\&( ?quot ?; ?)+', r' " '),                              # HTML espace codes
        (r'\b([a-zA-Z]{1,2}\.[a-zA-Z]{1,2}) \.( ?,?)', r'\1.\2'),     # fix tokenization issue with fullstop: e.g., B.S., Ph.D, ...
        (r"([a-zA-Z0-9])\@([a-zA-Z0-9])" , r"\1 @ \2"),    # email address
        (r'(\d)([-\\\/:]+)(\d)' , r'\1 \2 \3'),
        (r'([a-zA-Z0-9])([-\+\/:\(\)\[\]"\'\`\&\%\$\^\*\#])' , r'\1 \2'), 
        (r'([-\+\/:\(\)\[\]"\'\`\&\%\$\^\*\#])([a-zA-Z0-9])' , r'\1 \2'),
        (r" ' s\b" , r" 's"),                                        # fix 's cases broken by previous two lines
#        (r"([:;,\.\!\?\-\(\[])([''\"])" , r"\1 \2"),                    # fix :'... to be : '....
#        (r"([''\"])([:;,\.\!\?\-\)\]])" , r"\1 \2"),                    # fix ...') to be ....' )
        (r"([:;,\.\!\?\-\(\[])([''\"\(\)\[\]])" , r"\1 \2"),                    # fix :'... to be : '....
        (r"([''\"\(\)\[\]])([:;,\.\!\?\-\)\]])" , r"\1 \2"),                    # fix ...') to be ....' )
        (r"\b([a-zA-Z0-9]+)\. " , r"\1 . "),                         # 1. , a. , ...
        (r"([a-zA-Z0-9]+)(\.{2,})" , r"\1 \2"),                      # however... --> however ...
        (r"(\.{2,})([a-zA-Z0-9]+)" , r"\1 \2"),                      # ...but -->  ... but
        (r"\b(https?) ?:\/ ?\/ ?" , r"\1:\/\/"),                      # http:// and  https://        
        (r" ?\. ?(com|org|edu) ?\/ ?([a-zA-Z0-9]+)" , r".\1\/\2"),   # fix broken http:// ... .com/page.htm
    )
    return tok_regex
#    return od(tok_regex) # od was supposed to retain order.. but it didn't


import json, traceback

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


                                                                                                
if __name__ == '__main__':
    prs = argparse.ArgumentParser(description="""
    This script converts ukwac corpus to xml using TAGGER role labeler as a
    sentence parser.
    """)
    prs.add_argument('-d', '--dir',
                     help='Specify directory where ukwac files are located.',
                     required=False)
    prs.add_argument('-f', '--file',
                     help='Specify ukwac file to process. If not specified '
                          'default "ukwac.fixed-nowiki.node{SGE_TASK_ID}.gz" '
                          'is used.',
                     required=False)
    """
    prs.add_argument('-b', '--bin',
                     default=os.path.join(os.getcwd(), 'tagger',
                                          'morfette'),
                     help='Specify full path to TAGGER dir. If not '
                          'specified current directory + /tagger is used. '
                          'This option won\'t work with -qs option.',
                     required=False)
"""
    prs.add_argument('-o', '--out', default=os.getcwd(),
                     help='Specify output directory. If not specified current '
                          'dir is used.',
                     required=False)
    prs.add_argument('-qs', '--qsub', action='store_true',
                     help='Use this option if you run the script on forbin'
                          ' with qsub. The script will copy the required files'
                          ' under its /local instance dir and copy the results'
                          ' to /local/pavels.',
                     required=False)
    prs.add_argument('-pv', '--pverbs', action='store_true',
                     help='Specify this option if you want to switch phrasal'
                          'verbs search and to include them into the results.',
                     required=False)
    prs.add_argument('-missing', '--missing',
                     help='Specify the directory with the files converted ' +
                     'by ukwac_converter.py to check for any missed files.',
                     required=False)
    prs.add_argument('-c', '--cleanup',  action='store_true',
                     help='Should I clean up tagger input and output temporary files?',
                     required=False)
    args = prs.parse_args()
    if args.missing:
        detect_missing_files(args.missing)
        exit(0)
    taggers=[]
    mydir=os.path.dirname(os.path.realpath(__file__))
    
    """
    taggers.append( TAGGER('morfette',
                        os.path.join(mydir, '../../morfette-en/morfette-0.4.4.x86_64'),
                        #tagger_params='predict /home/ymarton/tools/morfette-en/wsj+lemma_00-18.mrg.utf8.morfetteready.v0.4.4.model',
                        tagger_params='predict ' + os.path.join(mydir, '../../morfette-en/wsj+lemma_00-18.mrg.utf8.morfetteready.750k.v0.4.4.model'),
                        preproc=lambda sents: '\n\n'.join( ['\n'.join([w for w in sent.split()]) for sent in sents] ),
                        #postproc=lambda toklines: ' '.join( [(tokline.strip().split(' ')[1] if len(tokline.strip().split(' ')) >= 3 else '\n') for tokline in toklines] ).split(" \n "),
                        #postproc=lambda toklines: ' '.join( [(tokline.strip().replace(' ','/') if len(tokline) >= 3 else '\n') for tokline in toklines] ).split(" \n "),
                        postproc=lambda toklines: ' '.join( [(tokline.strip().replace('/','_SLSH_').replace(' ','/') if len(tokline) >= 3 else '\n') for tokline in toklines] ).split(" \n "),
                        #unpackInXml=lambda sent: ' '.join( [t.split('/')[1] for t in sent.split()] ),
                        unpackInXml=lambda sent:  "\n\t\t%s\n\t" % sent.replace(' ','\n\t\t'),
                        isqsub=args.qsub))
"""
    
    taggers.append( TAGGER('spacy',
#                        os.path.join(mydir,'./myspacy.py'),
                        os.path.join(mydir,'./myspacy-emptyEngTok.py'),
                        tagger_params='',
                        preproc=lambda sents: '\n'.join(sents), 
                        #postproc=lambda toklines: ' '.join( [(tokline.strip().replace(' ','/') if len(tokline) >= 3 else '\n') for tokline in toklines] ).split(" \n "),
                        postproc=lambda toklines: ' '.join( [(tokline.strip().replace('/','_SLSH_').replace(' ','/') if len(tokline) >= 3 else '\n') for tokline in toklines] ).split(" \n "),
                        unpackInXml = lambda sent:  "\n\t\t%s\n\t" % sent.replace(' ','\n\t\t'),
                        isqsub=args.qsub))
   
    """
    taggers.append( TAGGER('open-sesame-20180823',
        os.path.join(mydir,'./run-open-sesame-20180823'),
        tagger_params='',
        preproc=lambda sents: '\n'.join(sents),
        postproc=lambda toklines:
            ['  '.join(group) for _, group in groupby(
                ' '.join( [(tokline.strip().replace('/','_SLSH_').replace(' ','/') if len(tokline) >= 3 else '\n') for tokline in toklines] ).split(" \n "), # token sub-elements are tab-separated, tokens are space-sep, each list item is a sentence 
                key=lambda sent: ' '.join([tok.split('\t')[1] for tok in sent.strip().split(' ')]))
            ] ,
        unpackInXml = lambda sent:  "\n\t\t%s\n\t" % sent.replace(' ','\n\t\t'),
        useStdin=False,
        isqsub=args.qsub))
"""
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
    """
    taggers.append( TAGGER('animate-person-tagger-wordnet',
        os.path.join(mydir,'./animate-person-tagger-wordnet.py'),
        tagger_params='',
        preproc=lambda sents: '\n'.join(sents), 
        postproc=lambda toklines: ' '.join( [(tokline.strip().replace('/','_SLSH_').replace(' ','/') if len(tokline) >= 3 else '\n') for tokline in toklines] ).split(" \n "),
        unpackInXml = lambda sent:  "\n\t\t%s\n\t" % sent.replace(' ','\n\t\t'),
        useStdin=True,
        isqsub=args.qsub))
        
    taggers.append( TAGGER('wsd-lesk-wordnet',
        os.path.join(mydir,'./wsd-lesk-wordnet.py'),
        tagger_params='',
        preproc=lambda sents: '\n'.join(sents),
        #postproc=lambda sents: '\n'.join(sents),
        useStdin=True,
        isqsub=args.qsub))


    taggers.append( TAGGER('amalgram',              # output contains also SpaCy NER, since Amalgram NER is not SotA
        os.path.join(mydir,'./my-amalgram'),
        tagger_params='',
        preproc=lambda sents: '\n'.join(sents),
        #postproc=lambda sents: '\n'.join(sents),
        postproc=lambda toklines: ' '.join( [(tokline.strip().replace('/','_SLSH_').replace('\t','/') if len(tokline) >= 3 else '\n') for tokline in toklines] ).split(" \n "),
        unpackInXml = lambda sent:  "\n\t\t%s\n\t" % sent.replace(' ','\n\t\t'),                           
        useStdin=False,
        isqsub=args.qsub))
"""
    
    ukwac_convert(args, taggers)

    ### uncomment to generate script execution .png graph
    # graphviz = GraphvizOutput()
    # graphviz.output_file = 'ukwac.png'
    # with PyCallGraph(output=graphviz):
#    ukwac_convert(args)
