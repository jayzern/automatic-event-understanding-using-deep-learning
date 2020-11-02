# coding: utf-8

# Yuval Marton, 10/2018
# based on code from Hong et al 2018

# TODO: Maybe use sentence boundaries as well?
# Full dataset conversion takes ~28.75h. Maybe less if you have > 16GB of RAM.

import glob
import operator
import pickle
import xml.etree.cElementTree as ET
import gzip
import re
from time import time

import numpy as np

from nltk.stem import WordNetLemmatizer
from nltk.corpus import wordnet as wn
wnl = WordNetLemmatizer()

import utils
import os

CODE_VER = "v2" # v1: legacy (Tony's). v2: with Frames/Animacy (Yuval's)

import roles
ROLES_CLS = roles.Roles2Args3Mods  #roles.Roles4Args3Mods  # roles.Roles3Args4Mods   # roles.Roles3Args3Mods 
#TRAIN_ROLES = ROLES_CLS.TRAIN_ROLES
#TEST_ROLES  = ROLES_CLS.TEST_ROLES
#ROLE_PRD    = ROLES_CLS.ROLE_PRD

USE_FRAMENET = False
USE_ANIM1 = False
USE_SENTI2 = False
USE_FRAMES_AND_ANIM = USE_FRAMENET or USE_ANIM1 or USE_SENTI2 #  True # False

if USE_FRAMES_AND_ANIM:
    FrAnSuff = ""
else:
    FrAnSuff = "NoFrAn"
    
if USE_FRAMENET:
    #FRAMES_PATH = '/users/yuvalm/data/rw-eng-with-raw-sentences-and-heads-but-no-malt/exp5-408/frames-fn1.7.txt'
    FRAMES_PATH = '/home/ymarton/data/FrameNet/frames-fn1.7.txt'
    FrAnSuff += "Fr"
if USE_ANIM1:
    ANIM_HMN = "Sentient"
    ANIM_NE_PERSON = "PERSON"
    ANIM_NONE = "None"
    ANIMS = {ANIM_NONE: 0, "Animate": 1, ANIM_HMN: 2}
    FrAnSuff += "An"
if USE_SENTI2:
    ANIMS_CLS = roles.Senti2_3vals
#    ANIM_HMN = "Sentient"
#    ANIM_NE_PERSON = "PERSON"
    ANIM_NONE = ANIMS_CLS.ANIM_NONE  #u"None"# inanimate
    ANIMS = ANIMS_CLS.ANIMS    
    FrAnSuff += "An2" + ANIMS_CLS.__name__
    
BATCH_SIZE = 128  # Mini-batch size for RNN

NUM_DEV_FILES   =   [ 217, 435, 651, 868,  1085,1302,1519,1736,
                     1953,2170,2387,2604,  2821,3038,3255,3472] #[0, 1100, 2200, 3300] #4 #14
NUM_TEST_FILES  =   [ 218, 436, 652, 869,  1086,1303,1520,1737,
                     1954,2171,2388,2605,  2822,3039,3256,3473] #[1, 1101, 2201, 3301] #4 #14
NUM_TRAIN_FILES =   0.01     # 0.01                  # 40 #400 #36 #None  # None for all except dev and test files taken first; fraction for uniform sampling fraction of the files not in dev or test; 1.0 for all except any dev or test

#FILES_PATH = '/home/ymarton/data/rw-eng/ukwac-proc-out-merged/heads.ukwac.fixed-nowiki.node*.converted.xml.converted.xml.gz'
#FILES_PATH = '/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20190223-merged/heads.ukwac.fixed-nowiki.node*.converted.xml.converted.xml.gz'
FILES_PATH = FILES_PATH = '../../../../../../../media/data-disk/data/annot/heads.ukwac.fixed-nowiki.node*.converted.xml.converted.xml.gz'
#FILES_PATH = '/media/ymarton/HDD2T/data/rw-eng/ukwac-proc-out-20200229-merged/heads.ukwac.fixed-nowiki.node*.converted.xml.converted.xml.gz'
#'/root/home/yuvalm/src/sem-fitl/event-embedding-multitask/data/rw-eng-1.0-*.converted.xml.gz'
#'/local/xhong/corpus/oct_2016_heads/heads.ukwac.fixed-nowiki.node*.converted.xml.gz'

#OUTPUT_PATH = '/home/ymarton/data/rw-eng/ukwac-proc-out-merged/exp6-48+a2+a345+am-other/'
#'/local/xhong/data/oct_data/'
#OUTPUT_PATH = '/home/ymarton/data/rw-eng/ukwac-proc-out-preproc4DL-20190929/exp2_0.01-2-2-%s/' % CODE_VER
#OUTPUT_PATH = '/home/ymarton/data/rw-eng/ukwac-proc-out-preproc4DL-20190929/exp9_%s-%d-%d-%s-%s-%s/' % (NUM_TRAIN_FILES, len(NUM_DEV_FILES), len(NUM_TEST_FILES), ROLES_CLS.__name__, FrAnSuff, CODE_VER)
OUTPUT_PATH = '../../../../../seq_event-rep/test_exp9_%s-%d-%d-%s-%s-%s/' % (NUM_TRAIN_FILES, len(NUM_DEV_FILES), len(NUM_TEST_FILES), ROLES_CLS.__name__, FrAnSuff, CODE_VER)

#wnl = WordNetLemmatizer()


def penn2wn(first):
    '''Converts P.O.S. tag from Penn TreeBank style to WordNet style
    '''
    if first == 'j':
        return wn.ADJ
    elif first == 'n':
        return wn.NOUN
    elif first == 'r':
        return wn.ADV
    elif first == 'v':
        return wn.VERB
    return None

"""
def convert_d_to_word(d):
    ''' Convert text in <dep> tag of the labelled corpus to a triple of 
        lemma, first letter of P.O.S. tag and position index
    '''
    # skip attributes of algorithm equal to FAILED
    algorithm = d.attrib.get('algorithm', 'VERB').upper()
    if algorithm == 'FAILED':
        return (None, None, None)

    # if d is a multiword expression, then return None
    words = d.text.lower().split()
    if len(words) > 1:
        return (None, None, None)

    triple = words[0].split("/") # words (or lemmas actually) are in the form lemma/pos/index
    lemma = triple[0].strip()
    pos_tag = triple[1].strip()
    index = triple[2].strip()

    if lemma == '' or pos_tag == '':
        return (None, None, None)
    
    # ignore stopwords without P.O.S. tag in a list
    first = pos_tag[0]
    if first not in ['n', 'v', 'j', 'r']:
        return (None, None, None)

    # ignore any entry with numbers or punctuations
    if re.search(r"[^a-zA-Z']+", lemma):
        return (None, None, None)

    # if a apostrophe is found, ignore it and letters behind it 
    apo_ix = lemma.find("'")
    if apo_ix != -1:
        lemma = lemma[:apo_ix]

    # perform lemmatization
    lemma = wnl.lemmatize(lemma, penn2wn(first))
    
    return lemma, pos_tag, index
"""

def convert_d_to_word(d):
    ''' Convert text in <dep> tag of the labelled corpus to a triple of 
        lemma, first letter of P.O.S. tag and position index
    '''
    # skip attributes of algorithm equal to FAILED
    algorithm = d.attrib.get('algorithm', 'VERB').upper()
    if algorithm == 'FAILED':
        return (None, None, None)

    # if d is a multiword expression, then return None
    words = d.text.lower().split()
    if len(words) > 1:
        return (None, None, None)

    triple = words[0].split("/") # words (or lemmas actually) are in the form lemma/pos/index
    lemma = triple[0].strip()
    pos_tag = triple[1].strip()
    index = triple[2].strip()

    if lemma == '' or pos_tag == '':
        return (None, None, None)
    
    # ignore stopwords without P.O.S. tag in a list
    first = pos_tag[0]
    if first not in ['n', 'v', 'j', 'r']:
        return (None, None, None)

    # ignore any entry with numbers or punctuations
    if re.search(r"[^a-zA-Z']+", lemma):
        return (None, None, None)

    # if a apostrophe is found, ignore it and letters behind it 
    apo_ix = lemma.find("'")
    if apo_ix != -1:
        lemma = lemma[:apo_ix]

    # perform lemmatization
    lemma = wnl.lemmatize(lemma, penn2wn(first))
    
    return lemma, pos_tag, index


def build_word_vocabulary(train_files, num_words=50000):
    ''' Build vocabulary using files in list
    '''
    word_counts = {}

    for j, f in enumerate(train_files):

        print("%d/%d \t %s" % (j + 1, len(train_files),
            (train_files[j] if len(train_files[j]) <=60 else train_files[j][:25]+"..."+ train_files[j][-35:])))

        try:
            xml = ET.fromstring(gzip.GzipFile(f).read())
        except:
            print("Problem with %s" % f)
            continue

        for arg_node in xml.findall("s/Frame/Arg"):
            lemmas = arg_node.attrib.get('lemmas').strip().split(' ')
            for lemma in lemmas:
                word_counts[lemma] = word_counts.get(lemma, 0) + 1

    word_vocabulary = dict((w, i) for i, w in enumerate(
        wc[0] for wc in reversed(sorted(list(word_counts.items()), key=operator.itemgetter(1))[-num_words:])
    ))

    print("Word vocabulary size is %d" % len(word_vocabulary))

    return word_vocabulary, word_counts


def build_frame_vocabulary():
    with open(FRAMES_PATH, "r") as ff:
        frame_vocabulary = dict( (frame.strip(),fi) for (fi,frame) in enumerate(ff) if frame.strip() )
    print("Frame vocabulary size is %d" % len(frame_vocabulary))
    return frame_vocabulary

    
def write_description(role_vocabulary, anim_vocabulary, word_vocabulary, frame_vocabulary,
                      unk_role_id,     unk_anim_id,     unk_word_id,     unk_frame_id,
                      missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
                      minibatch_size, dev_files, test_files, train_files):
    ''' Write data description to output file
    '''

    with open(OUTPUT_PATH + "description", "w+b") as output:
        data = {
            'word_vocabulary': word_vocabulary,
            'unk_word_id': unk_word_id,
            'missing_word_id': missing_word_id,
            
            'role_vocabulary': role_vocabulary,
            'unk_role_id': unk_role_id,
            'missing_role_id': missing_role_id,
            
            'frame_vocabulary':frame_vocabulary,
            'unk_frame_id': unk_frame_id,
            'missing_frame_id': missing_frame_id,
            
            'anim_vocabulary': anim_vocabulary,
            'unk_anim_id': unk_anim_id,
            'missing_anim_id': missing_anim_id,
            
            'minibatch_size': minibatch_size,
            
 #           'NN_missing_word_id': nn_missing_word_id,
 #           'NN_unk_word_id': nn_unk_word_id,
            'dev_files': dev_files,
            'test_files': test_files,
            'train_files': train_files
        }
        pickle.dump(data, output, protocol=pickle.HIGHEST_PROTOCOL)

    with open(OUTPUT_PATH + "description.txt", "w") as output:
        data = {
            'word_vocabulary_size': len(word_vocabulary),
            'top_20_words': ";".join(list(word_vocabulary.keys())[:20]),
            'unk_word_id': unk_word_id,
            'missing_word_id': missing_word_id,

            'role_vocabulary_size': len(role_vocabulary),
            'role_vocabulary': role_vocabulary,
            'unk_role_id': unk_role_id,
            'missing_role_id': missing_role_id,
            
            'frame_vocabulary_size': len(frame_vocabulary),
            #'frame_vocabulary': frame_vocabulary,
            'top_20_frames': ";".join(list(frame_vocabulary.keys())[:20]),
            'unk_frame_id': unk_frame_id,
            'missing_frame_id': missing_frame_id,
            
            'anim_vocabulary_size': len(anim_vocabulary),
            'anim_vocabulary': anim_vocabulary,
            'unk_anim_id': unk_anim_id,
            'missing_anim_id': missing_anim_id,
            
            'minibatch_size': minibatch_size,
 #           'NN_missing_word_id': nn_missing_word_id,
 #           'NN_unk_word_id': nn_unk_word_id,
            'dev_files': dev_files,
            'test_files': test_files,
            'train_files': train_files
        }
        output.write("\n".join("%s=%s" % (k,v) for (k,v) in data.items()))

        
def convert_file(file, dataset_type,
                 role_vocabulary, anim_vocabulary, word_vocabulary, frame_vocabulary,
                 unk_role_id,     unk_anim_id,     unk_word_id,     unk_frame_id,
                 missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
                 ):
    ''' Convert one XML file of laballed corpus into data for NN_RF
    '''
    file_nn_output = ""
    file_cwi_output = ""

    file_ngram_rf = ""
    file_roles = []
    file_words = []
    file_predicate_beginnings = []

    if unk_role_id != len(role_vocabulary):
        print("WARNING! unk_role_id != len(role_vocabulary)")
    if unk_word_id != len(word_vocabulary):
        print("WARNING! unk_word_id != len(word_vocabulary)")
    #unk_role_id = len(role_vocabulary)
    #unk_word_id = len(word_vocabulary)
    ## missing word must come before unk for nonincremental model, 
    ## because in 'nothing' model we want to predict missing words, but we never predict unk words.
    nn_missing_word_id = len(word_vocabulary)
    nn_unk_word_id = len(word_vocabulary) + 1
    reverse_word_vocabulary = utils.get_reverse_map(word_vocabulary)

    print(("len(word_vocabulary) = %d" % len(word_vocabulary)))
    print(("vocab = %s ..." % ([k for k in word_vocabulary][:15])))
          
    MAX_WARNINGS = 5
    numof_warnings = 0
    
    try:
        xml = ET.fromstring(gzip.GzipFile(file).read())
    except:
        print("Problem with %s" % file)
        return "", ""

    for s in xml.findall("s"):
        skip_sentence = False
        sentence_nn_output = ""
        content_word_indices = []

        sentence_ngram_rf = ""        
        sentence_roles = []
        sentence_words = []
        sentence_predicate_beginnings = []

        for p in s.findall("predicate"):
            predicate_roles = {}
            predicate_words = {}

            # Sample for non-incremental model 
            #sample = dict((r, nn_missing_word_id) for r in (role_vocabulary.values() + [unk_role_id]))
            if USE_FRAMES_AND_ANIM:
                sample = dict((r, (missing_word_id,missing_anim_id,missing_frame_id)) for r in set(list(role_vocabulary.values()) + [unk_role_id]))
            else:
                sample = dict((r, missing_word_id) for r in set(list(role_vocabulary.values()) + [unk_role_id]))

            for d in p.findall("dependencies/dep"):
                word, pos_tag, index = convert_d_to_word(d)
                if word is None:
                    continue  # skip - otherwise cant compare to N-gram
                anim_id = unk_anim_id
                frame_id= unk_frame_id
                role = d.get("type").upper()
                role_id = role_vocabulary.get(role, unk_role_id)
                
                # multiple words with the same role within a predicate make evaluation hard to compare
                # so skip examples with multiple args of same role (but allow multiple modifiers of same role)
#                if sample[role_id] != nn_missing_word_id and dataset_type != 'train':
                if (  (USE_FRAMES_AND_ANIM and (sample[role_id][0] != missing_word_id)) \
                   or (not USE_FRAMES_AND_ANIM and (sample[role_id] != missing_word_id))) \
                and not (((len(role) >= 2) and (role[:2] == "AM")) \
                      or ((len(role) >= 4) and (role[:4] == "ARGM"))) :
                    numof_warnings += 1
                    if numof_warnings < MAX_WARNINGS:
                        print(("WARNING %d/%d: skipping example with role %s:%s, word %s:%s, in sample:s '%s':'%s'" % (numof_warnings, MAX_WARNINGS, role,role_id, word,index, sample,ET.tostring(s)[:60])))
#                        print("WARNING: skipping example with multiple args of same role: '%s'" % fr_node)
                    if numof_warnings == 1:
                        print(("roles: %s" %  role_vocabulary))
                    skip_sentence = True
                    break
                
                # index of the first word. Will be used for ordering the samples. 
                # -1 to convert 1-based indexing into 0-based one.
                i = int(d.text.split()[0].split("/")[-1])

                word_id    = word_vocabulary.get(word, unk_word_id)
                nn_word_id = word_vocabulary.get(word, nn_unk_word_id)
                
                content_word_indices.append(i)                
                #sample[role_id] = nn_word_id
                predicate_roles[i] = role_id
                #predicate_words[i] = word_id
                if USE_FRAMES_AND_ANIM:
                    predicate_words[i] = (word_id,anim_id,frame_id)
                    sample[role_id] = (word_id,anim_id,frame_id)
                else:
                    predicate_words[i] = word_id
                    sample[role_id]    = word_id                
            if skip_sentence:
                break

            if len(predicate_roles) == 0:
                continue

            sentence_nn_output += "%r\n" % sample
            sorted_predicate_roles = [r for i, r in sorted(predicate_roles.items())]     
            sorted_predicate_words = [w for i, w in sorted(predicate_words.items())]
            predicate_beginnings = [1] + [0] * (len(sorted_predicate_words) - 1)

            sentence_roles += sorted_predicate_roles
            sentence_words += sorted_predicate_words
            sentence_predicate_beginnings += predicate_beginnings
            sentence_ngram_rf += " ".join(
                [reverse_word_vocabulary.get(w, "<unk>") for w in sorted_predicate_words]) + "\n"
            
        if skip_sentence:
            continue

        file_nn_output += sentence_nn_output
        file_cwi_output += (str(content_word_indices) + "\n")

        file_roles += sentence_roles
        file_words += sentence_words
        file_predicate_beginnings += sentence_predicate_beginnings
        file_ngram_rf += sentence_ngram_rf

    print(("Number of multiple arg warnings: %d / %d %d %d" % (numof_warnings, len(file_nn_output), len(file_roles), len(file_words))))

    #return file_nn_output, file_cwi_output, file_roles, file_words, file_predicate_beginnings, file_ngram_rf
    return file_nn_output, file_roles, file_words


def convert_file_v2(file, dataset_type,
                 role_vocabulary, anim_vocabulary, word_vocabulary, frame_vocabulary,
                 unk_role_id,     unk_anim_id,     unk_word_id,     unk_frame_id,
                 missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
                 ):
    ''' Convert one XML file of laballed corpus into data for NN_RF
    '''
    file_nn_output = ""
    file_roles = []
    file_words = []

    MAX_WARNINGS = 5
    numof_warnings = 0

    ROLE_PRD = ROLES_CLS.ROLE_PRD
    
    if unk_role_id != len(role_vocabulary):
        print("WARNING! unk_role_id != len(role_vocabulary)")
        
#    unk_role_id = len(role_vocabulary)
#    unk_word_id = len(word_vocabulary)
    # missing word must come before unk for nonincremental model, 
    # because in 'nothing' model we want to predict missing words, but we never predict unk words.
#    nn_missing_word_id = len(word_vocabulary)
#    nn_unk_word_id = len(word_vocabulary) + 1

    reverse_word_vocabulary = utils.get_reverse_map(word_vocabulary)

    try:
        xml = ET.fromstring(gzip.GzipFile(file).read())
        print(("v2 converting %s" % file)) # DBG
    except:
        print("Problem with %s" % file)
        return "", ""

    for s in xml.findall("s"):
#        skip_sentence = False
        sentence_nn_output = ""
#        content_word_indices = []

        sentence_roles = []
        sentence_words = []
#        sentence_predicate_beginnings = []

        for fr_node in s.findall("Frame"):
            skip_frame = False
            predicate_roles = {}
            predicate_words = {}
            role_order_dict = {}

            ## Sample for non-incremental model 
            #sample = dict((r, nn_missing_word_id) for r in (role_vocabulary.values() + [unk_role_id]))
            #sample = dict((r, (unk_word_id,unk_anim_id,unk_frame_id)) for r in (role_vocabulary.values() + [unk_role_id]))
            if USE_FRAMES_AND_ANIM:
                sample = dict((r, (missing_word_id,missing_anim_id,missing_frame_id)) for r in set(list(role_vocabulary.values()) + [unk_role_id]))
            else:
                sample = dict((r, missing_word_id) for r in set(list(role_vocabulary.values()) + [unk_role_id]))
             
            for arg_node in fr_node.findall("Arg"):
                # To prevent invalid literal ValueError
                try:

                    arg_head = arg_node.attrib.get('head')
                    if not arg_head:
                        continue  # skip
                    
                    role = arg_node.attrib.get('role')
                    if not role:
                        continue  # skip
                    role = role.upper()
                    
    #                if role in ("ARG3","ARG4","ARG5"):
    #                    role = "ARG3-4-5"
    #                elif (role[:4] == "ARGM") and (role not in ("ARGM-LOC", "ARGM-TMP", "ARGM-MNR")):
    #                    role = "ARGM-OTHER"
                    role = ROLES_CLS.adjustRole(role)
                        
    #                if role not in role_vocabulary:
    #                    role = ROLE_OTHER

                    word_id = word_vocabulary.get(arg_head, unk_word_id)
                    role_id = role_vocabulary.get(role, unk_role_id)
                    
                    arg_tokens =   arg_node.attrib.get('tokens',"").strip().split(' ')
                    head_idx = int(arg_node.attrib.get('head_index'))
                    arg_start= int(arg_node.attrib.get('span_begin'))
                    head_rel_idx = head_idx - arg_start
                        
                    if USE_FRAMES_AND_ANIM:
                        anim = ""
                        frame_name = ""
                        if (0 <= head_rel_idx < len(arg_tokens)):
                            head_tok_flds = arg_tokens[head_rel_idx].split('/')
                            try:
                                if role == ROLE_PRD:
                                    frame_name = head_tok_flds[16]
                                    anim = ANIMS_CLS.ANIM_PRD if USE_SENTI2 else ANIM_NONE
                                else:
                                    if USE_SENTI2:
                                        if len(head_tok_flds) < 25:
                                            print(("ERROR: too short format for token %d: %s, file: %s" % (head_rel_idx, arg_tokens[head_rel_idx], file)))
                                            sys.exit(-1)
                                        anim = head_tok_flds[18]
                                        # TODO: add other SNT2 fields (19-24)
                                    elif USE_ANIM1:
                                        anim = head_tok_flds[14]
                                        ne   = head_tok_flds[12]
                                        if (ne == ANIM_NE_PERSON) or (arg_head in ("i","me","myself", "we","us","ourselves", "you","yourself", "he","him", "himself", "she", "her", "herself")):
                                            anim = ANIM_HMN
                            except Exception as e:
                                print(("BUG! Received exception %s" % e))
                                raise #pass
                        anim_id = anim_vocabulary.get(anim, unk_anim_id)
                        frame_id= frame_vocabulary.get(frame_name, unk_frame_id)
                        if anim_id == unk_anim_id:
                            print("\tDBG: anim: %s, anim_id: %d, head_rel_idx %d = head_idx %d - arg_start %d, \t len(arg_tokens)=%d,\t arg_tokens[head_rel_idx]=%s" % (anim, anim_id, head_rel_idx, head_idx, arg_start,  len(arg_tokens), arg_tokens[head_rel_idx]))
                        
                    # multiple words with the same role within a predicate make evaluation hard to compare
                    # so skip examples with multiple args of same role (but allow multiple modifiers of same role)
    #                if sample[role_id] != nn_missing_word_id and dataset_type != 'train':
                    if (  (USE_FRAMES_AND_ANIM and (sample[role_id][0] != missing_word_id)) \
                    or (not USE_FRAMES_AND_ANIM and (sample[role_id] != missing_word_id))) \
                    and not (((len(role) >= 2) and (role[:2] == "AM")) \
                        or ((len(role) >= 4) and (role[:4] == "ARGM"))) :
                        numof_warnings += 1
                        if numof_warnings < MAX_WARNINGS:
                            print(("WARNING %d/%d: skipping example with role %s:%s, arg_head %s, in sample:fr_node '%s':'%s'" % (numof_warnings, MAX_WARNINGS, role,role_id, arg_head, sample,ET.tostring(fr_node)[:100])))
    #                        print("WARNING: skipping example with multiple args of same role: '%s'" % fr_node)
                        if numof_warnings == 1:
                            print(("roles: %s" %  role_vocabulary))                    
                        skip_frame = True
                        break
    #
    #                # index of the first word. Will be used for ordering the samples. 
    #                # -1 to convert 1-based indexing into 0-based one.
    #                i = int(d.text.split()[0].split("/")[-1])

    #                word_id = role_vocabulary.get(word, unk_word_id)
    #                nn_word_id = word_vocabulary.get(word, nn_unk_word_id)
                    
    #                content_word_indices.append(i)                
    #                sample[role_id] = nn_word_id
                    
                    predicate_roles[head_idx] = role_id
                    if USE_FRAMES_AND_ANIM:
                        predicate_words[head_idx] = (word_id,anim_id,frame_id)
                        sample[role_id] = (word_id,anim_id,frame_id)
                    else:
                        predicate_words[head_idx] = word_id
                        sample[role_id]           = word_id
                        role_order_dict[role_id] = int(head_idx)
                except:
                    pass
                
            # end Arg loop
            if skip_frame:
                break

            if len(predicate_roles) == 0:
                numof_warnings += 1 # go to next Frame
                continue

            # Reorder sample depending on order of word appearance
            ordered_sample = {k:sample[k] for k, v in sorted(role_order_dict.items(), key=lambda item: item[1])}
            for r in set(list(role_vocabulary.values()) + [unk_role_id]):
              if r not in ordered_sample:
                ordered_sample[r] = missing_word_id

            sentence_nn_output += "%r\n" % ordered_sample
            sorted_predicate_roles = [r for i, r in sorted(predicate_roles.items())]     
            sorted_predicate_words = [w for i, w in sorted(predicate_words.items())]

            sentence_roles += sorted_predicate_roles
            sentence_words += sorted_predicate_words

        # end Frame loop
#        if skip_sentence:
#            continue

        file_nn_output += sentence_nn_output
        file_roles += sentence_roles
        file_words += sentence_words
        
    # end S (sentence) loop

    print(("Number of multiple arg warnings: %d / %d %d %d" % (numof_warnings, len(file_nn_output), len(file_roles), len(file_words))))

#    return file_roles, file_words
    return file_nn_output, file_roles, file_words


def convert_data(input_files, dataset_type,
                 role_vocabulary, anim_vocabulary, word_vocabulary, frame_vocabulary,
                 unk_role_id,     unk_anim_id,     unk_word_id,     unk_frame_id,
                 missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
                 minibatch_size):
    '''Creates NN (RNN) datasets'''
    assert dataset_type in ('train', 'dev', 'test')

    all_nn_output = ""

    all_roles = []
    all_words = []

    my_convert_file = convert_file if (CODE_VER == "v1") else convert_file_v2
    
    for j, f in enumerate(input_files):
        print("%s %d/%d" % (dataset_type, j + 1, len(input_files)))

        file_nn_output, file_roles, file_words  = my_convert_file(f, dataset_type,
                                                               role_vocabulary, anim_vocabulary, word_vocabulary, frame_vocabulary,
                                                               unk_role_id,     unk_anim_id,     unk_word_id,     unk_frame_id,
                                                               missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
        )

        all_nn_output += file_nn_output
        all_roles += file_roles
        all_words += file_words

    with open(OUTPUT_PATH + "NN_" + dataset_type, "w") as nn_output:
        nn_output.write(all_nn_output)
    print(("converted %d words" % len(all_words)))


if __name__ == '__main__':
    t0 = time()

    if not os.path.exists(OUTPUT_PATH):
        print(("MKDIR %s" % OUTPUT_PATH))
        os.mkdir(OUTPUT_PATH)
    
#    all_files = glob.glob(FILES_PATH)
    all_files = sorted(glob.glob(FILES_PATH))
    all_files = [fn.replace("20190223", "20200229") for fn in all_files] # quick n dirty hack cuz didn't convert all files
    
    dev_files = all_files[:NUM_DEV_FILES] if (type(NUM_DEV_FILES) is int) else \
                sorted(list([all_files[fi] for fi in NUM_DEV_FILES]))
    print("=======dev=======\n%r" % dev_files)
    
    test_files = all_files[NUM_DEV_FILES:NUM_DEV_FILES + NUM_TEST_FILES] if (type(NUM_TEST_FILES) is int) else \
                 sorted(list([all_files[fi] for fi in NUM_TEST_FILES]))
    print("=======test=======\n%r" % test_files)

    if NUM_TRAIN_FILES is None:
        train_files = all_files[NUM_DEV_FILES + NUM_TEST_FILES:]
    elif type(NUM_TRAIN_FILES) is float:
        num_files = len(all_files)
        num_train_files = min( int(round(float(num_files) * NUM_TRAIN_FILES)),
                               len(all_files)-len(dev_files)-len(test_files) )
        step = 1.0 / NUM_TRAIN_FILES
        fi = 0
        i = 0
        train_files = set()
        while len(train_files) < num_train_files:
            if (all_files[fi] in dev_files) or (all_files[fi] in test_files) or (all_files[fi] in train_files):
                fi += 1
                fi = fi % num_files
                continue
            train_files.add(all_files[fi])
            i += 1
            fi = int(round(step * i)) % num_files
        train_files = sorted(list(train_files))
    else:
        train_files = all_files[NUM_DEV_FILES + NUM_TEST_FILES:NUM_DEV_FILES + NUM_TEST_FILES + NUM_TRAIN_FILES]
    print("=======train=======\n%r" % train_files)
    print("%d train files out of %d files" % (len(train_files), len(all_files)))

    word_vocabulary, word_counts = build_word_vocabulary(train_files)
    role_vocabulary = ROLES_CLS.TEST_ROLES if (CODE_VER == "v1") else ROLES_CLS.TRAIN_ROLES

    unk_word_id = len(word_vocabulary)
    missing_word_id = unk_word_id + 1

    if ROLES_CLS.has_role_other:
        print(("Role set has UNK role: %d" % ROLES_CLS.TRAIN_ROLES[Roles.ROLE_OTHER]))
        unk_role_id = ROLES_CLS.TRAIN_ROLES[Roles.ROLE_OTHER] 
    else:
        unk_role_id = len(role_vocabulary)
    missing_role_id = len(role_vocabulary) + 1  #unk_role_id + 1

    if USE_FRAMES_AND_ANIM:
        frame_vocabulary = build_frame_vocabulary() if USE_FRAMENET else {}
        unk_anim_id = len(set(ANIMS.values()))  # some string values may be intentionally mapped to same num codes
        unk_frame_id= len(frame_vocabulary)
        missing_anim_id = unk_anim_id + 1
        missing_frame_id= unk_frame_id + 1
    else:
        frame_vocabulary = {}
        ANIMS = {}
        unk_anim_id = None
        unk_frame_id= None
        missing_anim_id = None
        missing_frame_id= None
        
    write_description(ROLES_CLS.TEST_ROLES,  ANIMS,       word_vocabulary, frame_vocabulary,
                      unk_role_id, unk_anim_id, unk_word_id,     unk_frame_id,
                      missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
                      BATCH_SIZE, dev_files, test_files, train_files)
    print("Vocabulary building done in %d seconds" % (time() - t0))

    convert_data(dev_files, 'dev', 
                 role_vocabulary, ANIMS,           word_vocabulary, frame_vocabulary,
                 unk_role_id,     unk_anim_id,     unk_word_id,     unk_frame_id,
                 missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
                 BATCH_SIZE)
    convert_data(test_files, 'test',
                 role_vocabulary, ANIMS,           word_vocabulary, frame_vocabulary,
                 unk_role_id,     unk_anim_id,     unk_word_id,     unk_frame_id,
                 missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
                 BATCH_SIZE)
    convert_data(train_files, 'train',
                 role_vocabulary, ANIMS,           word_vocabulary, frame_vocabulary,
                 unk_role_id,     unk_anim_id,     unk_word_id,     unk_frame_id,
                 missing_role_id, missing_anim_id, missing_word_id, missing_frame_id,
                 BATCH_SIZE)

    print("Conversion done in %d seconds" % (time() - t0))
    print("DON'T FORGET:   cp  %s/*  ../data/test/" % OUTPUT_PATH)
