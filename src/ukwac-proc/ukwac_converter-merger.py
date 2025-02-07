#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
This script uses ukwac corpus AND output from various taggers (POS taggers, parers, lemmatizer, SRL, etc.)
sentences and taggers' outputs are aligned and collected in order. 
The result is written as xml file.
The script consists of two classes and several functions that work with these
classes. 
Here is a brief description of the conversion procedure.
Conversion procedure:
done in ukwac_converver.py :
    1. Read ukwac file contents.
    2. Normalize contents by removing non-utf8 symbols.
    3. Extract the sentences, 
    4. Expand various contractions like "I'm, you're, let's".
    5. Write extracted ukwac sentences into an input file.
    6. Feed the input file to each tagger
done here: 
    7. Collect their outputs, and input-sentence-align them.
    8. Create xml representation and write it to disk.
    9. Clean up temp input, output files.
Performance:
    Depending on the taggers you use (see __main__ below)

Example call:
python ~/src/sem-fit/ukwac-proc/ukwac_converter-merger.py -f /home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/heads.ukwac.fixed-nowiki.node3388.converted.xml.gz  -t '[["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/",["rawsent","predicate"]],["/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-malt-but-no-heads/",["malt"]],["/home/ymarton/data/rw-eng/ukwac-proc-out-20181101/tmp2/",["morfette","wsd-lesk-wordnet","open-sesame-20181002","animate-person-tagger-wordnet","spacy","he_srl"]]]' -o  /home/ymarton/data/rw-eng/ukwac-proc-out-20190120/merged/

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
import json

__author__ = "Yuval Marton yuvalmarton@gmail.com, based on work by p.shkadzko@gmail.com"


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
        ugly = et.tostring(root, 'utf-8', method='xml')
        parsed_xml = mdom.parseString(ugly)
        nice_xml = parsed_xml.toprettyxml(indent=" " * 3)
        even_more_nice_xml = rxml_header.sub('', nice_xml)
        even_more_nice_xml = re.sub(r'\s*?\n\s*\n','\n', even_more_nice_xml) # Yuval 20190910: get rid of empty lines
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

        input_file_path = os.path.join(curpath, input_file)
        output_file_path = os.path.join(curpath, output_file)
        call = ' '.join([self.tagger_bin, self.tagger_params,
                         ' < ' if self.useStdin else '', input_file_path,
                         ' > ' if self.useStdin else '', output_file_path])
        print 'running tagger %s ...' % self.tagger_bin
        try:
            sb.check_call([call], shell=True)
        except sb.CalledProcessError:
            errmsg = "ERROR: calling tagger binary, please see " + \
                  "\"tagger._shell_call()\" method"
            print(errmsg)
            sys.exit(errmsg)

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
        #sents_list = sents.split('\r\n``\r\n')
        #print 'sentences extracted:', len(sents_list) - 1
        print 'sentences extracted:', len(sents)
        print 'tagger READS:', input_fname
        print 'tagger WRITES:', output_fname
        try:
            with open(os.path.join(os.getcwd(), input_fname), 'w') as f:
                f.write(self.preproc(sents))
        except Exception as ex:
            errmsg = 'EXCEPTION on {0}: {1}\n{2}'.format(gethostname(), input_fname, ex)
            print(errmsg)
            exit(errmsg)
        tmp_output_fname = output_fname + '.tmp'
        self._shell_call(input_fname, tmp_output_fname, 0)

        try:
            with open(os.path.join(os.getcwd(),  tmp_output_fname), 'r') as tmpf:
                outsents = tmpf.readlines()
        except Exception as ex:
            errmsg = 'EXCEPTION on{0}: {1}\n{2}'.format(gethostname(), tmp_output_fname,  ex)
            print(errmsg)
            exit(errmsg)
        #print "outsents"
        #print outsents[:10]
        try:
            with open(os.path.join(os.getcwd(),  output_fname), 'w') as f:
                if len(outsents) > 1:
                    f.write('\n'.join(line.strip() for line in self.postproc(outsents)) )
                else:
                    f.write('\n'.join(self.postproc(outsents[0].strip().split('\n'))) )
        except Exception as ex:
            errmsg = 'EXCEPTION on {0}: {1}\n{2}'.format(gethostname(), output_fname, ex)
            print(errmsg)
            exit(errmsg)
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
    rtext_id = re.compile(r'<text>(.*?)</text>')
    ids = rtext_id.findall(clean_data)
    rfilename = re.compile(r'<filename>(.*?)</filename>')
    orig_filenames = rfilename.findall(clean_data)

    if len(sents) == 0:
        rtokens = re.compile(r'<rawsent>(.*?)</rawsent>')
        sents = rtokens.findall(clean_data)
    if len(ids) == 0:
        rtext_id = re.compile(r'(?:<text |<rawsent>)[\s\r\n]*(.*?)(?:/>|</rawsent>)', re.MULTILINE)
        ids_tmp = rtext_id.findall(clean_data)
        ids = []
        last_id = ""
        for i in range(len(ids_tmp)):
            if ids_tmp[i][:3] == "id=":   
                last_id = ids_tmp[i]
                #print last_id
                continue #i += 1
            ids.append(last_id)
    if len( orig_filenames) == 0:
        orig_filenames = ids
        
    if len(sents) != len(ids) or len(ids) != len( orig_filenames):
        raise Exception("Format problem: %d sents, %d ids, %d orig_filenames" % (len(sents), len(ids), len( orig_filenames)))
    return sents,  orig_filenames, ids



def build_xml(orig_texts, orig_filenames, ids, ukwac_base1, ukwac_fname_base_converted_gz, result_fname, taggers, pverbs):
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

    COL_TOK_IDX      , COL_SPCY_TOK_IDX = 0,0
    COL_WF           , COL_SPCY_WF,COL_SESA_WF,COL_MRFT_WF,COL_SNT2_WF = 1,1,1,0,0  # 1,1,3,0
    COL_LEM_MRFT     , COL_MRFT_LEM     = 2,1
    COL_LEM_SPCY     , COL_SPCY_LEM     = 3,2
    COL_LEM_SESA     , COL_SESA_LEM     = 4,3  # 4,1
    COL_POS_SESA     , COL_SESA_POS     = 5,5
    COL_POS_MRFT     , COL_MRFT_POS     = 6,2
    COL_POS_MALT     = 7
    COL_CPOS_SPCY    , COL_SPCY_CPOS    = 8,3
    COL_FPOS_SPCY    , COL_SPCY_FPOS    = 9,4
    COL_DEPREL_SPCY  , COL_SPCY_DEPREL  =10,5
    COL_PRNT_IDX_SPCY, COL_SPCY_PRNT_IDX=11,6
    COL_NE_SPCY      , COL_SPCY_NE      =12,8
    COL_NE_BIO_SPCY  , COL_SPCY_NE_BIO  =13,9
    COL_ANIM_HMN_WN  , COL_WN_ANIM_HMN  =14,2
    COL_SYNSET_LESK  =15
    COL_FRAME_NAME   , COL_SESA_FRAMENAME=16,13
    COL_FRAME_LU     , COL_SESA_LU       =17,12

    COL_ANIM_HMN_SNT2,              COL_SNT2_ANIM_HMN                  =18,1  #    sentient-animate
    COL_NUM_STRT_SMBD,              COL_SNT2_NUM_STRT_SMBD             =19,2
    COL_NUM_STRT_SMTHN,             COL_SNT2_NUM_STRT_SMTHN            =20,3
    COL_NUM_NOT_STRT_SMBD_SMTHN,    COL_SNT2_NUM_NOT_STRT_SMBD_SMTHN   =21,4
    COL_NUM_NONSTRT_SMBD,           COL_SNT2_NUM_NONSTRT_SMBD          =22,5
    COL_NUM_NONSTRT_SMTHN,          COL_SNT2_NUM_NONSTRT_SMTHN         =23,6
    COL_NUM_NOT_NONSTRT_SMBD_SMTHN, COL_SNT2_NUM_NOT_NONSTRT_SMBD_SMTHN=24,7
    
    COL_SPCY_PRNT = 7
    
    ATTR_SRL_ROLE_HE      = "Role_He_et_al_2016"
    ATTR_SRL_ROLE_SENNA   = "Role_Senna_2004"
    ATTR_SRL_ROLE_SPAN_RW1= "Role_span_RW1"
    ATTR_SRL_ROLE_SPAN_HE = "Role_span_He_et_al_2016"
        
    TOK_ELMT_UNK = "__"

    def is_eligible_head(tok):
        return (tok[COL_SPCY_CPOS] not in ("PART","ADP","PUNCT","DET","CCONJ","CD","NUM"))
 
    numof_args_with_spacy_he_tok_mismatch = 0
    numof_args = 0
    numof_lemma_diffs = 0
    numof_wf_mismatch_sesame_spacy = 0
    numof_tok_count_mismatch_sesame_spacy = 0
    numof_tok_count_mismatch_he_spacy = 0
    numof_sentences_with_tok_count_mismatch = 0
    numof_sesame_unk = 0
    root = et.Element("i_m_groot")
    os.chdir(os.path.dirname(result_fname))  # cd into parent dir
    print "building XML with these taggers:\n" + '\n'.join(["\t%s" % str(tagger) for tagger in taggers])

    taggernameslists = [tagger[1] for tagger in taggers]
    taggernames =  [item for sublist in taggernameslists for item in sublist]
    # flatten list of lists: [item for sublist in list for item in sublist]
    print "Received the following tagger names: %s" % taggernames
    
    taggerfiles = [os.path.join(tagger_entry[0],ukwac_fname_base_converted_gz) for tagger_entry in taggers]
    taggerfiles[0] = taggers[0][0] + ukwac_base1 # RW v1 with heads
    taggerfiles[1] = taggers[1][0] + ukwac_base1 # RW v1 with malt parser
    taggerfiles[1] = taggerfiles[1].replace("heads.","") # remove prefix "heads." if exists in basename
    if taggers[0][0] == taggers[1][0]:
        del taggerfiles[1]
    print "Merging \n\t" + "\n\t".join(taggerfiles)
    taggers_data = [UkwacTools.gzip_reader(taggerfile) for taggerfile in taggerfiles]

    def fix_and_parse_xml(data):
        try:
            return et.fromstring(data)
        except: # Exception as e:
            try:
                return et.fromstring("<groot>" + data + "</groot>")
            except Exception as e:
                raise Exception("ERROR %s '%s' reading xml. First 10 lines: '%s'" % (e.__class__.__name__, e.message, data.split('\n')[:10]))
           
    #xml_roots = [ et.fromstring(tagger_data) for tagger_data in taggers_data]
    xml_roots = [ fix_and_parse_xml(tagger_data) for tagger_data in taggers_data]
               
    for snt_cnt,sent_views in  enumerate(izip(*[xml_root.iter('s') for xml_root in xml_roots])):
        sentence_has_tok_count_mismatch = False
        sent_node = et.SubElement(root, "s")

        for  ti,sent_per_tagger in enumerate(sent_views):
            #print "tagger %d: %s\n" % (ti, taggerfiles[ti])
            pretoktext = ""
            for attr in sent_per_tagger.attrib.iteritems():
                if attr[0] not in sent_node.attrib:
                    sent_node.set(attr[0], attr[1])
                elif sent_node.attrib[attr[0]] != attr[1]:
                    sent_node.set(attr[0], sent_node.attrib[attr[0]] + "; " + attr[1])

            for child in sent_per_tagger:               
#                if et.iselement(child):
                if et.iselement(child) and (child.tag in taggernameslists[ti]):    # Yuval 20200530
                    if child.tag == 'pre-tokenized':
                        if sent_node.find("rawtext") and (child.text.strip().lower() != sent_node.find("rawtext").text.strip().lower()):
                            raise Exception("mismatch at sentence %d: \n%s\nPre-tokenized='%s'\n" % (snt_cnt, et.tostring(sent_node), child.text))
                        pretoktext = child.text.strip().lower()
                        pretoktext_node_new_tag = 'tokenized'
                        if sent_node.find(pretoktext_node_new_tag) is None:
                            pretoktext_node = et.SubElement(sent_node, pretoktext_node_new_tag)
                            pretoktext_node.text = child.text.strip()
#                        print "DBG sent_node.get(child.tag)", sent_node.get(child.tag)
#                        if sent_node.find(child.tag):
#                            print "DBG sent_node.get(child.tag).text", (sent_node.find(child.tag).text if sent_node.find(child.tag).text else "")
#                            print "DBG child.text", (child.text if child.text else "")
#                        print
                    elif child.tag == 'predicate': # old SRL (SENNA) - copy its multiple xml nodes per sentence # Yuval 20200530
                        sent_node.append(child)
                    elif (sent_node.find(child.tag) is None) or (sent_node.find(child.tag).text.strip().lower() != child.text.strip().lower()):
#                        child.text = child.text.strip()  # Yuval 20190910
#                        if child.text != "":             # Yuval 20190910
                        if child.tag.lower() != "frame":  # Yuval 20200312 don't copy old semantic <Frame> elements
                            sent_node.append(child)

            """

            rawsent_text = et.SubElement(sent_node, "pre-tokenized")
            rawsent_text.text  = next(orig_texts_iter) 

            for ti in range(len(sent_per_tagger)):
                subElem[ti] = et.SubElement(sent_node, taggers[ti].name)
                subElem[ti].text = taggers[ti].unpackInXml(sent_per_tagger[ti])                 

            # add vps if set
#            if pverbs:
#                sent_node = UkwacTools.add_vps(sent_node)
"""
#            sent_cnt += 1

        # output unified view per SRL-included token, containing all annotations from all layers,
        # and split into predicate-dedicated nodes
        # (only predicate and its arguments in each node, potentially more than one node per sentence)

        tname = "he_srl"
        if tname in taggernames:
            he_srl_nodes = list(sent_node.iter(tname))
            if len(he_srl_nodes) != 1:
                raise Exception("Expected a single He++ SRL node, but received %d while merging node: %s" % (len(he_srl_nodes), et.tostring(sent_node)))
            he_srl_node = he_srl_nodes[0]
            he_srl_tok_lines = he_srl_node.text.strip().split("\n")
#        else:
#            print "skipping tagger %s - only got these:%s" % (tname, taggernames)    

        tname = "spacy"
        if tname in taggernames:
            spacy_nodes = list(sent_node.iter(tname))
            if len(spacy_nodes) != 1:
                raise Exception("Expected a single SpaCy node, but received %d while merging node: %s" % (len(spacy_nodes), et.tostring(sent_node)))
            spacy_node = spacy_nodes[0]
            spacy_tok_lines = spacy_node.text.strip().split("\n")
            spacy_tok_parts = []
            for tok_line in spacy_tok_lines:
                tok_parts =  tok_line.strip().split('/')
                while len(tok_parts) > 10 : # MWE tok bug fix:
                    if tok_parts[COL_SPCY_PRNT_IDX].isdigit():
                        tok_parts[COL_SPCY_PRNT] += "_" + tok_parts[COL_SPCY_PRNT + 1]
                        del tok_parts[COL_SPCY_PRNT + 1]
                    else:
                        tok_parts[COL_SPCY_LEM] += "_" + tok_parts[COL_SPCY_LEM + 1]
                        del tok_parts[COL_SPCY_LEM + 1]
                while len(tok_parts) > 10 : # another MWE tok bug fix:
                    tok_parts[COL_SPCY_WF] += "_" + tok_parts[COL_SPCY_WF + 1]
                    del tok_parts[COL_SPCY_WF + 1]
                tok_parts[COL_SPCY_WF] = tok_parts[COL_SPCY_WF].replace('_SLSH_', '/') # un-escape slash
                tok_parts[COL_SPCY_LEM]= tok_parts[COL_SPCY_LEM].replace('_SLSH_', '/') # un-escape slash
                spacy_tok_parts.append(tok_parts)
#        else:
#            print "skipping tagger %s - only got these:%s" % (tname, taggernames)

        tname = "animate-person-tagger-wordnet"
        if tname in taggernames:
            anim_nodes = list(sent_node.iter(tname))
            if len(anim_nodes) != 1:
                raise Exception("Expected a single animate-person-tagger-wordnet node, but received %d while merging node: %s" % (len(anim_nodes), et.tostring(sent_node)))
            anim_node = anim_nodes[0]
            anim_tok_lines = anim_node.text.strip().split("\n")
            anim_tok_parts = []
            for tok_line in anim_tok_lines:
                tok_parts = tok_line.strip().split('/')
                while len(tok_parts) > 3 : # MWE tok bug fix:
                    tok_parts[1] += "_" + tok_parts[1 + 1]
                    del tok_parts[1 + 1]
                while len(tok_parts) > 3 : # another MWE tok bug fix:
                    tok_parts[0] += "_" + tok_parts[0 + 1]
                    del tok_parts[0 + 1]
                anim_tok_parts.append( tok_parts )
#        else:
#            print "skipping tagger %s - only got these:%s" % (tname, taggernames)

        tname = "morfette"
        if tname in taggernames:
            mrft_nodes = list(sent_node.iter(tname))
            if len(mrft_nodes) != 1:
                raise Exception("Expected a single Morfette node, but received %d while merging node: %s" % (len(mrft_nodes), et.tostring(sent_node)))
            mrft_node = mrft_nodes[0]
            mrft_tok_lines = mrft_node.text.strip().split("\n")
            mrft_tok_parts = []
            for tok_line in mrft_tok_lines:
                tok_parts = tok_line.strip().split('/')
                while len(tok_parts) > 3 : # MWE tok bug fix:
                    tok_parts[COL_MRFT_LEM] += "_" + tok_parts[COL_MRFT_LEM + 1]
                    del tok_parts[COL_MRFT_LEM + 1]
                while len(tok_parts) > 3 : # another MWE tok bug fix:
                    tok_parts[COL_MRFT_WF] += "_" + tok_parts[COL_MRFT_WF + 1]
                    del tok_parts[COL_MRFT_WF + 1]
                mrft_tok_parts.append( tok_parts )
#        else:
#            print "skipping tagger %s - only got these:%s" % (tname, taggernames)

        tname = "senti-anim-wn" #"senti2"
        if tname in taggernames:
            snt2_nodes = list(sent_node.iter(tname))
            if len(snt2_nodes) != 1:
                raise Exception("Expected a single Senti2 node, but received %d while merging node: %s" % (len(snt2_nodes), et.tostring(sent_node)))
            snt2_node = snt2_nodes[0]
            snt2_tok_lines = snt2_node.text.strip().split("\n")
            snt2_tok_parts = []
            for tok_line in snt2_tok_lines:
                tok_parts = tok_line.strip().split('\t')
                snt2_tok_parts.append( tok_parts )
#        else:
#            print "skipping tagger %s - only got these:%s" % (tname, taggernames)


        tname = "open-sesame-20180823"
        if tname in taggernames:            
            sesame_nodes = list(sent_node.iter(tname)) #"open-sesame-20181002"))
            if len(sesame_nodes) != 1:
                raise Exception("Expected a single open-sesame node, but received %d while merging node: %s" % (len(sesame_nodes), et.tostring(sent_node)))
            sesame_node = sesame_nodes[0]
            sesame_frames =  sesame_node.text.strip().split("\n\t\t\n")
            sesame_frame_tok_parts = []
            for frame in sesame_frames:
                frame_tok_lines = []
                for frame_tok_line in frame.strip().split("\n"):
                    frame_tok_lines.append( frame_tok_line.strip().split('\t') )
                sesame_frame_tok_parts.append(frame_tok_lines)
#        else:
#            print "skipping tagger %s - only got these:%s" % (tname, taggernames)
            
        if True:            
            numof_args += len(he_srl_tok_lines)            
            he_srl_frames = {}
            for tok_line in he_srl_tok_lines:
                he_srl_tok_parts = tok_line.strip().split('\t')
                try:
                    if len(he_srl_tok_parts) != 6:
                        raise Exception                    
                    prd_idx = he_srl_tok_parts[0]
                    arg_start = he_srl_tok_parts[1]
                    arg_end   = he_srl_tok_parts[2]
                    role      = he_srl_tok_parts[3]
                    prd       = he_srl_tok_parts[4]
                    arg_phrase= he_srl_tok_parts[5]
                    if prd_idx not in he_srl_frames:
                        he_srl_frames[prd_idx] = []
                        he_srl_frames[prd_idx].append( (prd_idx,prd_idx, "PRD",prd,) )
                    
                    he_srl_frames[prd_idx].append( (arg_start,arg_end, role,arg_phrase,) )                       
                except:
                    if tok_line.strip() == "NOTHING_FOUND":
                        frame_node = et.SubElement(sent_node, "Frame")
                        frame_node.set("prd_idx", "None")
                    else:
                        raise Exception("Format problem with He++ token line '%s' in node: %s" % (tok_line, et.tostring(sent_node)))
            for prd_idx in he_srl_frames:
                frame_node = et.SubElement(sent_node, "Frame")
                frame_node.set("prd_idx", "%s" % prd_idx)
                frame_node.text = '\n\t' + '\n\t'.join( ['\t'.join(tok_parts) for tok_parts in he_srl_frames[prd_idx]] ) + '\n\t' 
                for tok_parts in he_srl_frames[prd_idx]:
                    arg_start = int(tok_parts[0])
                    arg_end   = int(tok_parts[1])
                    arg_phrase    =     tok_parts[3]
                    numof_merged_tokens = arg_phrase.count("'")     # TODO: fixed token alignment among taggers!
                    he_srl_arg_toks     = arg_phrase.strip().split(" ")
                    head_idx = -1
                    arg_node = et.SubElement(frame_node, "Arg")
                    arg_node.text = arg_phrase                      # TODO: change to head word?
                    arg_node.set("role",    tok_parts[2])
                    arg_node.set("span_begin", tok_parts[0])
                    arg_node.set("span_end",   tok_parts[1])
                    arg_node.set("phrase",     arg_phrase)
                    arg_node.set("lemmas",  " ".join(tok_parts[COL_MRFT_LEM] for tok_parts in mrft_tok_parts[arg_start:arg_end+1]))
                    arg_tokens = []
                    arg_tok_govnr_idx = []
                    for i in range(arg_start, arg_end+1):
                        try:
                            if (i >= len(spacy_tok_parts)): # or  (len(spacy_tok_parts) !=  len(he_srl_arg_toks)):    
                                numof_tok_count_mismatch_he_spacy += 1
                                arg_node.set("tokenization_mismatch", "True")
                                arg_node.set("tokenization_count_mismatch", "True")
                                print "WARNING: skipping arg '%s' due to token count mismatch between SpaCy (%d) and He++ arg (%d): '%s'" \
                                    % (arg_phrase,  len(spacy_tok_parts),  len(he_srl_arg_toks), ' '.join(he_srl_arg_toks))
                                break 
                            elif (he_srl_arg_toks[i-arg_start].lower() != spacy_tok_parts[i][COL_SPCY_WF].lower()):
#                                print "WARNING: skipping arg due to token mismatch between pre-tokenized text and He++: '%s' vs '%s' in node %s" \
#                                    % (he_srl_arg_toks[i-arg_start],  spacy_tok_parts[i][COL_SPCY_WF],  et.tostring(sent_node))
                                print "WARNING: in arg '%s': token mismatch between He++ and pre-tokenized text / SpaCy: '%s' vs '%s'" \
                                    % (arg_phrase, he_srl_arg_toks[i-arg_start],  spacy_tok_parts[i][COL_SPCY_WF], )
                                numof_args_with_spacy_he_tok_mismatch += 1
                                arg_node.set("tokenization_mismatch", "True")
                                #break
                            mrft_lemma = mrft_tok_parts [i][COL_MRFT_LEM].lower() if i < len(mrft_tok_parts) else ""
                            if  mrft_lemma != spacy_tok_parts[i][COL_SPCY_LEM] :
                                numof_lemma_diffs += 1
                                if numof_lemma_diffs < 10:
                                    print "WARNING: lemma variants %d: Morfette '%s' vs SpaCy '%s' at arg '%s'" \
                                        % (numof_lemma_diffs, mrft_lemma, spacy_tok_parts[i][COL_SPCY_LEM],  arg_phrase)
                                    
                            # open-sesame stuff:
                            framename = ""
                            frameLU = ""
                            if "open-sesame-20180823" in taggernames:  
                                sesame_lemma = sesame_frame_tok_parts[0][i][COL_SESA_LEM].lower() if (len(sesame_frame_tok_parts) > 0 and len(sesame_frame_tok_parts[0]) > i) else "";
                                sesame_pos   = sesame_frame_tok_parts[0][i][COL_SESA_POS] if (len(sesame_frame_tok_parts) > 0 and len(sesame_frame_tok_parts[0]) > i) else "";
                                if sesame_lemma in ("unk","UNK"):
                                    numof_sesame_unk += 1
                                elif  mrft_lemma != sesame_lemma :
                                    numof_lemma_diffs += 1
                                    if numof_lemma_diffs < 10:
                                        print "WARNING: lemma variants %d: Morfette '%s' vs Open Sesame '%s' at arg '%s'" \
                                            % (numof_lemma_diffs, mrft_lemma, sesame_lemma,  arg_phrase)

                                if (len(sesame_frame_tok_parts) > 0) and (i < len(sesame_frame_tok_parts[0])) \
                                and (sesame_frame_tok_parts[0][i][COL_SESA_WF].lower() != spacy_tok_parts[i][COL_SPCY_WF].lower()):
    #                                if sesame_frame_tok_parts[0][i][COL_SESA_WF] == "UNK":
    #                                    numof_sesame_unk += 1
    #                                elif
                                    if len(sesame_frame_tok_parts[0]) != len(spacy_tok_parts):
                                        numof_tok_count_mismatch_sesame_spacy += 1
                                        arg_node.set("tokenization_mismatch", "True")
                                        arg_node.set("tokenization_count_mismatch", "True")
                                        print "WARNING: tokenization count mismatch! Open-Sesame %d:'%s' vs SpaCy %d:'%s' in arg '%s'" \
                                            % (len(sesame_frame_tok_parts), ' '.join(tok[COL_SESA_WF] for tok in sesame_frame_tok_parts[0]), len(spacy_tok_parts),  ' '.join(tok[COL_SPCY_WF] for tok in spacy_tok_parts),  arg_phrase)
                                        break
                                    else:
                                        numof_wf_mismatch_sesame_spacy += 1
                                        arg_node.set("tokenization_mismatch", "True")
                                        print "WARNING: token mismatch! Open-Sesame '%s' vs SpaCy '%s' in arg '%s'" \
                                            % (sesame_frame_tok_parts[0][i][COL_SESA_WF], spacy_tok_parts[i][COL_SPCY_WF],  arg_phrase)
                                else:
                                    for fi in range(len(sesame_frame_tok_parts)):
                                        if (i < len(sesame_frame_tok_parts[fi])) :
                                            if sesame_frame_tok_parts[fi][i][COL_SESA_FRAMENAME] not in ("_",""):
                                                framename = sesame_frame_tok_parts[fi][i][COL_SESA_FRAMENAME]
                                                frameLU = sesame_frame_tok_parts[fi][i][COL_SESA_LU]
                                                break
                            else:
                                sesame_lemma = ""
                                sesame_pos   = ""

                            arg_tok = [
                                i      ,
                                mrft_tok_parts [i][COL_MRFT_WF], #spacy_tok_parts[i][COL_SPCY_WF]           ,
                                mrft_lemma                         ,
                                spacy_tok_parts[i][COL_SPCY_LEM].replace('/', '_SLSH_')     ,  # Yuval 20200315
                                sesame_lemma     ,
                                sesame_pos     ,
                                mrft_tok_parts [i][COL_MRFT_POS]      ,
                                COL_POS_MALT     ,
                                spacy_tok_parts[i][COL_SPCY_CPOS]    ,
                                spacy_tok_parts[i][COL_SPCY_FPOS]    ,
                                spacy_tok_parts[i][COL_SPCY_DEPREL]  ,
                                spacy_tok_parts[i][COL_SPCY_PRNT_IDX],
                                spacy_tok_parts[i][COL_SPCY_NE]      ,
                                spacy_tok_parts[i][COL_SPCY_NE_BIO]  ,
                                anim_tok_parts [i][COL_WN_ANIM_HMN]   if ("animate-person-tagger-wordnet" in taggernames) else "",
                                COL_SYNSET_LESK  ,
                                framename   ,
                                frameLU     ,
                            ]

                            if "senti-anim-wn" in taggernames:  #"senti2"
                                if len(mrft_tok_parts) == len(snt2_tok_parts):
                                    arg_tok.extend(snt2_tok_parts[i][1:])
                                else:
                                    print ("WARNING: len(mrft_tok_parts) = %d, len(snt2_tok_parts) = %d" % (len(mrft_tok_parts), len(snt2_tok_parts)))
                            else:
                                print ("WARNING: didn't find senti-anim-wn!")
                                
                            arg_tokens.append(arg_tok)

                            #if   spacy_tok_parts[int(spacy_tok_parts[i][COL_SPCY_PRNT_IDX])][COL_SPCY_CPOS] not in ("PART","ADP","PUNCT","DET"):  
                            #    arg_tok_govnr_idx.append( (int(spacy_tok_parts[i][COL_SPCY_PRNT_IDX]), 1)) # path len 1 to governor
                            #elif spacy_tok_parts[i][COL_SPCY_CPOS] not in ("PART","ADP","PUNCT","DET"):
                            arg_tok_govnr_idx.append((i, 0)) # path len 0: self as governor
                            #else:
                            #    arg_tok_govnr_idx.append((None, None)) # not eligible gov
                                
                        except Exception as e:
                            if "spacy" in taggernames:
                                print "spacy_tok_parts[i]", spacy_tok_parts[i]
                            if "open-sesame-20180823" in taggernames: 
                                print "sesame_frame_tok_parts", sesame_frame_tok_parts
                            exc_tb = sys.exc_info()[2]
                            raise Exception("Bad format caused exception '%s' at line %d in node \n%s" % (e, exc_tb.tb_lineno, et.tostring(sent_node)))
                    arg_node.set("tokens", ' '.join( '/'.join("%s" % tok_part for tok_part in tok) for tok in arg_tokens))

                    # find head token in arg:
                    COL_TG_GOV          = 0
                    COL_TG_PATHLEN2ROOT = 1
                    COL_SR_PATHLEN2ROOT = 0
                    COL_SR_RELPOS       = 1
                    arg_subtree_roots = {}
                    for ti in range(len(arg_tok_govnr_idx)):
                        tj = ti
                        #while (arg_start <= arg_tok_govnr_idx[tj][COL_TG_GOV] <= arg_end):
                        while (arg_start <= (tj+arg_start) <= arg_end):
                            #if tj == arg_tok_govnr_idx[tj][COL_TG_GOV] - arg_start: #root
                            if tj == int(spacy_tok_parts[tj+arg_start][COL_SPCY_PRNT_IDX]) - arg_start:
                                if is_eligible_head(spacy_tok_parts[tj+arg_start]): #(spacy_tok_parts[tj+arg_start][COL_SPCY_CPOS] not in ("PART","ADP","PUNCT","DET","CCONJ")):
                                    arg_tok_govnr_idx[tj] = (tj+arg_start, 0) # root
                                    arg_tok_govnr_idx[ti] = (tj+arg_start,  arg_tok_govnr_idx[ti][COL_TG_PATHLEN2ROOT]+1)
                                #print "WARNING: unexpected infinte loop with tj  %d with ti %d in arg '%s'; arg_tok_govnr_idx = %s, in sentence '%s'" % (tj, ti,  arg_phrase, arg_tok_govnr_idx, pretoktext)
                                break;
                            tj = int(spacy_tok_parts[tj+arg_start][COL_SPCY_PRNT_IDX]) - arg_start
                            #if tj == arg_tok_govnr_idx[tj][COL_TG_GOV] - arg_start:
                            #    break;
                            
                            if not (0 <= tj < len(arg_tok_govnr_idx)):
                            #    print "WARNING: tj out of bounds: %d with ti %d in arg '%s'" % (tj, ti,  arg_phrase)
                                break # token mismatch?
                            #if (0 <= tj < len(arg_tok_govnr_idx)) \
                            if is_eligible_head(spacy_tok_parts[tj+arg_start]):  #(spacy_tok_parts[tj+arg_start][COL_SPCY_CPOS] not in ("PART","ADP","PUNCT","DET","CCONJ")):
                                arg_tok_govnr_idx[ti] = (tj+arg_start, arg_tok_govnr_idx[tj][COL_TG_PATHLEN2ROOT]+1)
                            
                        if arg_tok_govnr_idx[ti][COL_TG_GOV] not in arg_subtree_roots.keys():
                            if is_eligible_head(spacy_tok_parts[ti+arg_start]):  #(spacy_tok_parts[ti+arg_start][COL_SPCY_CPOS] not in ("PART","ADP","PUNCT","DET","CCONJ")):
                                arg_subtree_roots[arg_tok_govnr_idx[ti][COL_TG_GOV]] = (arg_tok_govnr_idx[ti][COL_TG_PATHLEN2ROOT], ti) # path len and rel pos in arg
                                #arg_subtree_roots[arg_tok_govnr_idx[ti][COL_TG_GOV]] = (arg_tok_govnr_idx[ti][COL_TG_PATHLEN2ROOT], ti) # path len and rel pos in arg
                        """
                        subtree_rep_of_ti = arg_subtree_roots[arg_tok_govnr_idx[ti][COL_TG_GOV]]
                        if     (spacy_tok_parts[subtree_rep_of_ti[COL_SR_RELPOS]+arg_start][COL_SPCY_CPOS] in ("PART","ADP","PUNCT","DET")) \
                           or  ( (subtree_rep_of_ti[0] >  arg_tok_govnr_idx[ti][COL_TG_PATHLEN2ROOT]) \
                             and (spacy_tok_parts[ti+arg_start][COL_SPCY_CPOS] not in ("PART","ADP","PUNCT","DET")) \
                               ):
                            # closer to subtree root and is eligible for being head (e.g., not a preposition):
                            arg_subtree_roots[arg_tok_govnr_idx[ti][COL_TG_GOV]] = (arg_tok_govnr_idx[ti][COL_TG_PATHLEN2ROOT], ti)                 """
                        
                    arg_node.set("subtrees","%d" % len(arg_subtree_roots))
                    prev_stg = 1000000 #govrnr = 1000000
                    for stg in arg_subtree_roots.keys():
                        if prev_stg > stg: #govrnr > stg:
                            head_idx = stg # arg_subtree_roots[stg][COL_SR_RELPOS] + arg_start
                            prev_stg = stg #govnr = stg
                    #head_idx = arg_start + ti
                    if not (0 <= head_idx < len(mrft_tok_parts)):
                        head_idx = arg_start
                        for i in range(arg_start, arg_end+1):
                            if (i < len(mrft_tok_parts)) and (mrft_tok_parts[i][COL_MRFT_POS] not in ("TO","IN","DT",".",",")):
                                head_idx = i
                                break
                    arg_node.set("head_index", "%d" % head_idx)
                    arg_node.set("head",  (mrft_tok_parts[head_idx][COL_MRFT_LEM] if (0 <= head_idx < len(mrft_tok_parts)) else ""))
                    arg_node.text = arg_node.get("head") # for Asad
                    if arg_node.get("tokenization_count_mismatch") == "True":
                        sentence_has_tok_count_mismatch = True
        if (snt_cnt % 1000) == 0:
            print ".",
        if sentence_has_tok_count_mismatch:
            numof_sentences_with_tok_count_mismatch += 1
    print
    print "numof_lemma_diffs / numof args: %d / %d (%.2f%%)" % (numof_lemma_diffs, numof_args, (float)(numof_lemma_diffs) / numof_args * 100 if numof_args else 0.0 )
    print "numof_sesame_unk: %d / %d (%.2f%%)"  % (numof_sesame_unk , numof_args, (float)(numof_sesame_unk)  / numof_args * 100 if numof_args else 0.0 )
    print "numof_args_with_spacy_he_tok_mismatch: %d / %d (%.2f%%)" % (numof_args_with_spacy_he_tok_mismatch, numof_args, (float)(numof_args_with_spacy_he_tok_mismatch) / numof_args * 100 if numof_args else 0.0 )
    print "numof_wf_mismatch_sesame_spacy: %d / %d (%.2f%%)" % (numof_wf_mismatch_sesame_spacy, numof_args, (float)(numof_wf_mismatch_sesame_spacy) / numof_args * 100 if numof_args else 0.0 )
    print "numof_tok_count_mismatch_sesame_spacy (num of args): %d / %d (%.2f%%)"       % (numof_tok_count_mismatch_sesame_spacy      , numof_args, (float)(numof_tok_count_mismatch_sesame_spacy)       / numof_args * 100 if numof_args else 0.0 )
    print "numof_tok_count_mismatch_he_spacy (num of args): %d / %d (%.2f%%)"       % (numof_tok_count_mismatch_he_spacy      , numof_args, (float)(numof_tok_count_mismatch_he_spacy)       / numof_args * 100 if numof_args else 0.0 )
    print "numof_sentences_with_tok_count_mismatch: %d / %d (%.2f%%)" % (numof_sentences_with_tok_count_mismatch, snt_cnt+1, (float)(numof_sentences_with_tok_count_mismatch) / (snt_cnt+1) * 100 if (snt_cnt+1) else 0.0)
    print
    
    # appending formatted xml to the file
    UkwacTools.append_to_xml(result_fname, root)
    UkwacTools.gzip_xml(result_fname)


def ukwac_convert(args, taggers):
    """
    Main function.
    Merge all processing outputs in various xml files into a single xml file.
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
            sys.exit("ERROR: Please provide input dir or input file name.")
    try:
        os.mkdir(args.out)
    except OSError:
        print("Output directory already exists! %s" % args.out)

    # Start ukwac conversion
    isqsub = args.qsub
    for filename in files:    
        ukwac_fname_path = os.path.join(filename)
        ukwac_fname_base_converted = '.'.join([os.path.basename(ukwac_fname_path.strip('.gz')),
                                'converted.xml'])
        ukwac_base1 =  os.path.basename(ukwac_fname_path)
        ukwac_fname_base_converted_gz =  ukwac_fname_base_converted + ".gz"
        result_fname = os.path.join(os.getcwd(), args.out, ukwac_fname_base_converted) #  os.path.join(os.getcwd(), ukwac_fname_base_converted)
        print 'processing %s...' % filename
        print 'basenames: ', ukwac_base1, ukwac_fname_base_converted_gz
#        fdata = UkwacTools.gzip_reader(ukwac_fname_path)
#        print 'extracting sentences...'
        #sents, word_lemma, id_index, malt_dic = extract_ukwac_data(fdata)
#        sents,  orig_filenames, id_index  = extract_ukwac_data(fdata)

        """
        # make sure there are no consecutive identical sentences, because this will mess up output alignment:
        prev_sent = ""
        for i in xrange(1, len(sents)):
            #if i >= len(sents):
            #    break
            if sents[i].lower() == sents[i-1]:
                print "WARNING: duplicate input sentence %d: '%s'" % (i, sents[i])
                sents[i] += " ( DUPLICATE %d )" % i
                #del sents[i]
                #del orig_filenames[i]
                #del id_index[i]
                #i -= 1 # adjust position after deletion
 """                      

     

        print 'creating xml...'
        #build_xml(word_lemma, id_index, result_fname, malt_dic, args.pverbs)
#        build_xml(sents,  orig_filenames, id_index,  ukwac_base1,ukwac_fname_base_converted_gz, result_fname, taggers, args.pverbs)
        build_xml(None, None, None,  ukwac_base1, ukwac_fname_base_converted_gz, result_fname, taggers, args.pverbs)

        """
        if args.cleanup:
            print 'cleaning...'
            for tagger in taggers:
 #               tagger.clean_up(out_dir, grid_tagger_in, grid_tagger_out, result_fname)
                tagger.clean_up(out_dir, tagger.ifn, tagger.ofn, result_fname)
        else:
            print "Left behind temp files in %s, such as " % out_dir, grid_tagger_in, grid_tagger_out, result_fname
        print 'done\n'
"""


if __name__ == '__main__':
    taggers=[
        # two first tagger lines below are reserved; must stay in first two positions:
        ('/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-heads-but-no-malt/heads.' , ('rawsent', 'predicate')), # previous RW-eng version, heads
        ('/home/ymarton/data/rw-eng/rw-eng-with-raw-sentences-and-malt-but-no-heads/' , ('malt',)),                       # previous RW-eng version, malt
        #('/home/ymarton/src/sem-fit/ukwac-proc/headeval/',  ('rawsent', 'predicate')), # previous RW-eng version
        #('/home/ymarton/src/open-sesame/data/',  ('rawsent', 'predicate')), # previous RW-eng version
        #('/home/ymarton/data/rw-eng/ukwac-proc-out-20181101/tmp/', ('morfette', 'wsd-lesk-wordnet', 'open-sesame-20181002', 'animate-person-tagger-wordnet',  'spacy', 'he_srl',)),
        ('/home/ymarton/data/rw-eng/ukwac-proc-out-20181101/tmp2/', ('morfette', 'wsd-lesk-wordnet', 'open-sesame-20181002', 'animate-person-tagger-wordnet',  'spacy', 'he_srl',)),
#        ('/data/semfit/ukwac-proc-out/' ,                       ('morfette', 'spacy', 'wsd-lesk-wordnet')), # do we even want this sad tagger?
#        ('/data/semfit/ukwac-proc-out-2-sesame+anim/',          ('open-sesame-20181002', 'animate-person-tagger-wordnet')),
#        ('/data/semfit/ukwac-proc-out-3-He++RW-relabel-Yuval/', ('he_srl',)),
    ] # 'pre-tokenized'


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
    prs.add_argument('-t', '--taggers',
                     default=json.dumps(taggers),
                     help='Specify taggers output to merge as a list of (tagger_output_dir, tagger_names), e.g., %s. Filename will be based on input filename base (plus a suffix). First entry is reserved for RW v1 with head annotation; Second entry for v1 Malt (if not needed set its folser the same as the first item); third and on are for other tagger outputs.' % taggers,
                     required=False)
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
        
    
#    ukwac_convert(args, taggers)
    ukwac_convert(args, json.loads(args.taggers))

    ### uncomment to generate script execution .png graph
    # graphviz = GraphvizOutput()
    # graphviz.output_file = 'ukwac.png'
    # with PyCallGraph(output=graphviz):
#    ukwac_convert(args)
