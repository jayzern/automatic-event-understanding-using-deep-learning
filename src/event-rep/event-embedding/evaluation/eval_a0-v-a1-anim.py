# evaluate semantic fit by providing ProbBank predicate (verb) and arguments (role and head word)
# does NOT take roleset / verb class / frame info

import os
import sys
import time
import pickle
import gzip
import random

import numpy
from scipy.stats import spearmanr

# Configuration of environment
SRC_DIR = os.path.dirname((os.path.dirname(os.path.abspath(__file__))))
sys.path.append(SRC_DIR)

import model_builder
import config
import utils
import json
import re

from roles import *

MODEL_PATH = config.MODEL_VERSION
RF_EVAL_PATH = os.path.join(config.EVAL_PATH, 'rf/')
NUMOF_INPUT_COLS = 13
NOT_A_VERB = 'na'
NOT_IN_VOCAB = 'OOV'
NO_MAPPING   = 'NO_MAPPING'
DELIM_LEM_ANIM = '/'

def cappedAverage(vals):
    #return numpy.mean ([min(v, config.minPscore * 2) for v in vals])
    return numpy.mean ([((config.minPscore / 2) if v < config.minPscore/2 else min(v, config.minPscore * 2)) for v in vals])

class config:
    shdLowercase = True              # lowercase
    shdTruncConjunction = True       # use only first conjunct if arg value is "a and b"
    shdIgnoreMultiValsPerArg = False # use only the first value per arg
    shdFailMultiValsPerArg = True    # fail (predict 0) if more than one value per arg
    shdRemapOtherArg = False         # move value(s) of Other arg to A0 and/or A1
    shdRemapUnkArg = False            # move value(s) of UNK arg to A0 and/or A1 or Other
    shdPredictTrue4RemainingUnk=False # predict majority class (True) for any unk arg remaining from previous remapping, if any; otherwise skip
    shdPredictTrue4OovTarget = True  # predict majority class (True) for OOV triggers and verb-frame not in mapping cases
    shdPredictTrue4OovArg = False    # predict majority class (True) for OOV argument; otherwise let model predict using UNK token
    shdPredictTrue4NoAoA1 = True     # predict majority class (True) if received no a0, a1
    shldRemapMnr2Other = True        # some models do not have ArgM-MNR so such input will raise exception
    shdUseAnimFrame = True           # use Sentience/Animacy and frame info

    minPscore = 0.0001      # 0.003: acc 64% f 62%; 0.0001: f 74%; 0.00009: acc 56% f 71%
    aggr_func = numpy.mean         # options: max, numpy.mean, cappedAverage
    aggr_func_name = aggr_func.__name__
    aggr_func = staticmethod(aggr_func)

    
def eval_a0_v_a1_anim(model_name,model_and_ver, input_eval_filename, model=None, print_result=True, switch_test=False):
   
    if model:
        net = model
    else:
        description = model_builder.load_description(MODEL_PATH, model_and_ver)        
        net = model_builder.build_model(model_name, description)
        net.load(MODEL_PATH, model_and_ver, description)

    bias = net.set_0_bias()

    if print_result:
        print(net.role_vocabulary)

    if "/" in input_eval_filename:
 #       result_file = input_eval_filename + ".out." +  model_and_ver + '.txt'
        pass
    else:
 #       result_file = os.path.join(MODEL_PATH, model_and_ver + '_' + input_eval_filename )
        input_eval_filename = os.path.join(RF_EVAL_PATH, input_eval_filename)

    if input_eval_filename[-4:] != '.txt':
        input_eval_filename += '.txt'
 #   if  result_file[-4:] != '.txt':
 #       result_file += '.txt'
  
    probs = []
    baseline = []
    oov_count = 0
    Arg = {}
    aggr_func = config.aggr_func
    frameNameRe = re.compile(r'^\d+-([^~]+)~.*$')
    
    if print_result:
        print(input_eval_filename)
        print("="*60)

    # dataset format: a0 v a1 score plausible(y/n)
    dataset = numpy.genfromtxt(input_eval_filename, dtype=str, delimiter='\t', usecols=list(range(NUMOF_INPUT_COLS))) #[0,1,2,3,4])
    dataset = numpy.append(dataset, [ ('dummy',)*4 + ("",)*(NUMOF_INPUT_COLS-4)], axis=0) # add dummy line to force last data point aggregated calcualtion
    
    if print_result:
#        print "\t".join( ("ID", "(roleset)", "A0", "V", "A1", "Loc", "Tmp", "Mnr", "Other", "UNK-role", "score", "plausible", "predictedProb", "predictedPlaus", "PredictPlausCorrect?", "comments") )
        print("\t".join( ("ID", "(roleset)", "A0", "V", "A1", "Loc", "Tmp", "Mnr", "Other", "UNK-role",
                          "score", "plausible",
                          "predictedProb", "predictedPlaus", "PredictPlausCorrect?",
                          "PairPredictedProbs", "MinPairPredictedProb", "PairPredictedPlaus", "PairPredictPlausCorrect?",
                          "comments") ))

    num_correct = 0
    confusion = { "gold %s" % True: {True: 0, False: 0},
                  "gold %s" %False: {True: 0, False: 0}}
    aggr_num_correct = 0
    aggr_confusion = { "gold %s" % True: {True: 0, False: 0},
                      "gold %s" %False: {True: 0, False: 0}}
    aggr_data_size = 0
    
    i = 0
    skipped = 0
    numofNotVerb = 0
    numofOOV = 0
    numofNoMapping = 0
    numofUnhandledUnks = 0
    currSetId = ""
    currSetPScores = []
    input_config = ""
    input_roles_words = {}
    for line in  dataset:
        i += 1
#        if i <= 1:
#            continue # skip header line
#        print line
#        if (len(line[0]) > 8) and (line[0][:8] == "##Config"):
        if "Config:" in line[0]:
            input_config += line[0] + "; "
            continue
        if (len(line[0]) == 0) or (line[0][0] == "#"):
            continue # skip empty and commented out lines

        ## iput semantic arg processing:
        #comment = ""
        isMultiValArg = False
        isOovArg = False
        ## frame/roleset a0 v a1 a2 a3 a4 a5 ArgM-MNR ArgM-LOC ArgM-TMP ArgM-MOD Other score plausible
        ## frame/roleset a0 v a1  ArgM-MNR ArgM-LOC ArgM-TMP Other(arg+argM) score plausible
        Arg = {}
        Arg["ID"]      = line[0]
        Arg["roleset"] = line[1]
        Arg["A0"]      = line[2]
        Arg["V"]       = line[3]
        Arg["A1"]      = line[4]
        Arg["MNR"]     = line[5]
        Arg["LOC"]     = line[6]
        Arg["TMP"]     = line[7]
        Arg["Other"]   = line[8]
        Arg["UNK"]     = line[9]
        score        = line[10]
        plausible    = (line[11].lower() == 'yes') or (line[11].lower() == 'true')
        comment      = (line[12] + "; ") if line[12] else ""
        #print "Arg right after assign", Arg

        frameName = frameNameRe.sub(r"\1", Arg["ID"])
        #print frameName

        if Arg["Other"] :
            otherArgs = Arg["Other"].split("; ")
            comment += "Received %s Other arg; " % (len(otherArgs) if len(otherArgs)>1 else "")
            if  config.shdRemapOtherArg:
                if len(otherArgs) == 1:
                    if not Arg["A1"]:
                        Arg["A1"] = otherArgs[0]
                        Arg["Other"] = ""
                        comment += "unpacked Other to A1; "
                    elif not Arg["A0"]:
                        Arg["A0"] = otherArgs[0]
                        Arg["Other"] = ""
                        comment += "unpacked Other to A0; "
                """
                elif len(otherArgs) >= 2:
                    if (not Arg["A0"]) and (not Arg["A1"]):
                        Arg["A0"] = otherArgs[0]
                        Arg["A1"] = otherArgs[1]
                        Arg["Other"] = "; ".join(otherArgs[2:])
                        comment += "unpacked Other to A0 A1; "
                    else:
                        comment += "Donno how to remap Other in: %s; " % line
                """       
        if Arg["UNK"] :
            otherArgs = Arg["UNK"].split("; ")
            comment += "Received %s UNK arg; " % (len(otherArgs) if len(otherArgs)>1 else "")
            if  config.shdRemapUnkArg:
                if len(otherArgs) == 1:
                    if not Arg["A1"]:
                        Arg["A1"] = otherArgs[0]
                        Arg["UNK"] = ""
                        comment += "unpacked UNK to A1; "
                    elif not Arg["A0"]:
                        Arg["A0"] = otherArgs[0]
                        Arg["UNK"] = ""
                        comment += "unpacked UNK to A0; "
                    elif not Arg["Other"]:
                        Arg["Other"] = otherArgs[0]
                        Arg["UNK"] = ""
                        comment += "unpacked UNK to Other (proxy for a2); "
                """
                elif len(otherArgs) >= 2:
                    if (not Arg["A0"]) and (not Arg["A1"]):
                        Arg["A0"] = otherArgs[0]
                        Arg["A1"] = otherArgs[1]
                        Arg["UNK"] = "; ".join(otherArgs[2:])
                        comment += "unpacked UNK arg to A0 A1; "
                    else:
                        comment += "Donno how to remap UNK arg in: %s; " % line
                """                           
 #       if A0 not in net.word_vocabulary:
 #           if print_result:
 #                print "%s MISSING FROM VOCABULARY. SKIPPING..." % A0

        #print "Arg before MNR remap", Arg
        if config.shldRemapMnr2Other and Arg["MNR"]:
            Arg["Other"] = ("%s; %s" % (Arg["Other"], Arg["MNR"])) if Arg["Other"] else Arg["MNR"]
            Arg["MNR"] = ""
        #print "Arg after MNR remap", Arg
        
        isOovTarget = False
        isNoMapping = False
        if (not Arg["V"]) or (Arg["V"] in (NOT_A_VERB, NOT_IN_VOCAB, NO_MAPPING)) :
            msg = "SKIPPED"
            if Arg["V"] == NOT_A_VERB:
                numofNotVerb += 1
                msg += " (no verb)"
            elif Arg["V"] == NOT_IN_VOCAB:
                numofOOV += 1
                isOovTarget = True
                msg += " (OOV)"
            elif Arg["V"] == NO_MAPPING:
                numofNoMapping += 1
                isNoMapping = True
                msg += " (no mapping)"
            if  (not Arg["V"]) or (Arg["V"] == NOT_A_VERB) or not config.shdPredictTrue4OovTarget:
                skipped += 1
                comment +=  "Received no V or trigger is not a verb or OOV -- Skipping %s; " % line
                if print_result:
                    print("\t".join( (Arg["ID"], ("(%s)" % Arg["roleset"]), Arg["A0"], Arg["V"], Arg["A1"], Arg["LOC"],Arg["TMP"],Arg["MNR"], Arg["Other"],Arg["UNK"], score, str(plausible), "", "",  msg, comment ) ))
                continue
        
        isNoA0A1 = False
        if not Arg["A0"] and not Arg["A1"] and not isOovTarget and not isNoMapping:
            isNoA0A1 = True
            comment +=  "Received no A0 or A1 args: %s; " % line
            if not config.shdPredictTrue4NoAoA1:
                skipped += 1
                if print_result:
                    print("\t".join( (Arg["ID"], ("(%s)" % Arg["roleset"]), Arg["A0"], Arg["V"], Arg["A1"], Arg["LOC"],Arg["TMP"],Arg["MNR"], Arg["Other"],Arg["UNK"], score, str(plausible), "", "",  "SKIPPED (no a0,a1)", comment ) ))
                continue
            
        isUnhandledUnk = False
        if Arg["UNK"]:
            isUnhandledUnk = True
            numofUnhandledUnks += 1
            comment +=  "Unhandled unknown args: %s; " % line
            #if not config.shdPredictTrue4RemainingUnk:
            if (not config.shdPredictTrue4RemainingUnk) and len(currSetPScores) > 1 and  currSetId == Arg["ID"]:
                skipped += 1
                if print_result:
                    print("\t".join( (Arg["ID"], ("(%s)" % Arg["roleset"]), Arg["A0"], Arg["V"], Arg["A1"], Arg["LOC"],Arg["TMP"],Arg["MNR"], Arg["Other"],Arg["UNK"], score, str(plausible), "", "",  "SKIPPED (unk args)", comment ) ))
                continue
#        if Arg["Other"]:
#            comment += "Warning: Unsupported role for %s. Ignoring argument; " % Arg["Other"]

        # if new set of inputs, aggregate over previous set and print rep score for set:
        if  currSetId != Arg["ID"] :
            if len(currSetPScores) > 0:
                aggr_data_size += 1
                currSetPScore =  aggr_func(currSetPScores)
                currSetPPlaus = currSetPScore >= config.minPscore
                if pplaus == plausible:
                    aggr_num_correct += 1
                aggr_confusion["gold %s" % currSetPlausible][currSetPPlaus] += 1
                if print_result:
                    print("\t".join( (currSetId, "(------)", "----", "----", "----", "----","----","----", "----","----", currSetScore, str(currSetPlausible), "---","---","---","---", ("%.5f" % currSetPScore), str(currSetPPlaus), ("CORRECT" if (currSetPPlaus == currSetPlausible) else "INCORRECT"), "SET SCORE (Aggregated)" ) ))
                    print()
            currSetId = Arg["ID"]
            currSetPScores = []
            currSetScore = score
            currSetPlausible = plausible
        ## TODO: check if score and plausible changed among the set records
        if Arg["ID"] == "dummy":
            i -= 1
            break;     # dummy line to force aggregated calc of last line
        
        # prepare model:
        roles = list(net.role_vocabulary.values())
        if net.missing_role_id < len(roles):
            del roles[net.missing_role_id] 
        unk_role_id = net.unk_role_id #len(roles) - 1 #roles[net.unk_role_id]
        if net.unk_role_id < len(roles):
            del roles[unk_role_id]   #roles[net.unk_role_id]
        

        input_roles_words = dict((r, net.missing_word_id) for r in (roles))
        input_roles_anims = dict((r, net.missing_anim_id) for r in (roles)) 
#        for (modelArgName, InputArgName) in { 'A0':"A0", 'A1':"A1", 'AM-LOC':"LOC", 'AM-TMP':"TMP", 'AM-MNR':"MNR",  '<UNKNOWN>':"Other"}.iteritems():    #  '<UNKNOWN>':"UNK"
        for (modelArgName, InputArgName) in { 'A0':"A0", 'A1':"A1", 'AM-LOC':"LOC", 'AM-TMP':"TMP", 'AM-MNR':"MNR",  Roles.ROLE_OTHER:Roles.TEST_ROLE_OTHER}.items():    #  '<UNKNOWN>':"UNK"
            if Arg[InputArgName]:
                if config.shdFailMultiValsPerArg:
                    if len(Arg[InputArgName].split("; ")) > 1:
                        comment += "Force failing due to multi-value arg %s: '%s'; " % (InputArgName, Arg[InputArgName],)
                        isMultiValArg = True
                        continue
                if config.shdIgnoreMultiValsPerArg:
                    if len(Arg[InputArgName].split("; ")) > 1:
                        comment += "Truncated arg %s from '%s' to: '%s'; " % (InputArgName, Arg[InputArgName], Arg[InputArgName].split("; ")[0])
                    Arg[InputArgName] = Arg[InputArgName].split("; ")[0]
                    #Arg[argName] = Arg[InputArgName]
                if config.shdTruncConjunction:
                    if len(Arg[InputArgName].split(" and ")) > 1:
                        comment += "Truncated arg %s from '%s' to: '%s'; " % (InputArgName, Arg[InputArgName], Arg[InputArgName].split(" and ")[0])
                    Arg[InputArgName] = Arg[InputArgName].split(" and ")[0]
                    Arg[InputArgName] = Arg[InputArgName].split("; ")[0]
                    #Arg[argName] = Arg[InputArgName]
                if config.shdLowercase:
                    if Arg[InputArgName] != Arg[InputArgName].lower():
                        comment += "Lowercasing '%s' to '%s'; " % (Arg[InputArgName], Arg[InputArgName].lower())
                    Arg[InputArgName] = Arg[InputArgName].lower()
                    #Arg[argName] = Arg[InputArgName]
                if Arg[InputArgName].split(DELIM_LEM_ANIM)[0] not in net.word_vocabulary:
                    isOovArg = True
                    numofOOV += 1
                    if print_result:
                        comment += "'%s' MISSING FROM VOCABULARY; " % Arg[InputArgName]
                if (InputArgName == "TMP") or (InputArgName == "Other"):  # '<UNKNOWN>'):
                    if len(input_roles_words) >= 6 and net.role_vocabulary[modelArgName] not in input_roles_words:
                        #print "DBG before delete", input_roles_words.keys(), input_roles_words.__class__.__name__
                        del input_roles_words[net.role_vocabulary['AM-MNR']] # should check if MNR empty...
                        del input_roles_anims[net.role_vocabulary['AM-MNR']]
                        comment += "added %d:Other role %s instead of MNR; " % (unk_role_id,Arg["Other"])
                        #print "DBG after del", comment, input_roles_words.keys()
                        #input_roles_words[unk_role_id] = utils.input_word_index(net.word_vocabulary, Arg[InputArgName], net.unk_word_id, warn_unk=True)
                    
                input_roles_words[net.role_vocabulary[modelArgName]] = utils.input_word_index(net.word_vocabulary, Arg[InputArgName].split(DELIM_LEM_ANIM)[0], net.unk_word_id, warn_unk=True)
                anim = Arg[InputArgName].split(DELIM_LEM_ANIM)[1] if (DELIM_LEM_ANIM in Arg[InputArgName]) else ""
                input_roles_anims[net.role_vocabulary[modelArgName]] = net.anim_vocabulary[anim] if anim in  net.anim_vocabulary else net.unk_anim_id
                #print Arg[InputArgName], ": anim = ", anim
 
        #print "Arg after ArgName,arg loop", Arg
        
        if   config.shdFailMultiValsPerArg and isMultiValArg:
            pscore = 0
            p_pairwise = [0,]
            comment += "Force-failing; "
        elif (config.shdPredictTrue4OovTarget and (isOovTarget or isNoMapping)) \
          or (config.shdPredictTrue4OovArg    and isOovArg) \
          or (config.shdPredictTrue4NoAoA1    and isNoA0A1) \
          or (config.shdPredictTrue4RemainingUnk and isUnhandledUnk):
            pscore = config.minPscore
            p_pairwise = [config.minPscore,]
            comment += "Predicting majority class; "
        else:
            Vrep = utils.input_word_index(net.word_vocabulary, Arg["V"], net.unk_word_id, warn_unk=True)
            frameRep = net.frame_vocabulary[frameName] if frameName in net.frame_vocabulary else net.unk_frame_id
            if frameName != "null" and  frameName not in net.frame_vocabulary:
                comment += "; WARNING: unknown frame '%s'" % frameName

            x_w_i, x_r_i, x_f_i, x_a_i, \
            y_w_i, y_r_i, y_f_i, y_a_i = ( #, bicknell, context, a1  = (
                numpy.asarray([[v for (k,v) in input_roles_words.items()],], dtype=numpy.int64),         # x_w_i
                numpy.asarray([[k for (k,v) in input_roles_words.items()],], dtype=numpy.int64),         # x_r_i
                numpy.asarray([[net.missing_frame_id for (k,v) in input_roles_words.items()],], dtype=numpy.int64),         # x_f_i
                numpy.asarray([[v for (k,v) in input_roles_anims.items()],], dtype=numpy.int64),         # x_a_i
                
                numpy.asarray([Vrep,],                     dtype=numpy.int64),                            # y_w_i 
                numpy.asarray([net.role_vocabulary["V"],], dtype=numpy.int64),                            # y_r_i
                numpy.asarray([frameRep,],                 dtype=numpy.int64),                            # y_f_i
                numpy.asarray([net.missing_anim_id,],      dtype=numpy.int64),                            # y_a_i
                
#                [0.0,], # 0.0],                                                                                     # scores
#                "\"" + Arg["A0"] + " " + Arg["V"] + "\"",                                                                     # context
#                [Arg["A1"],] # Arg["A1"]]
            )
            try:
                p = net.p_words2(x_w_i, x_r_i, x_f_i, x_a_i,
                                 y_w_i, y_r_i, y_f_i, y_a_i)
                pscore = p[0]
            except Exception as e:
                print("Error %s with args '%s' and input_roles_words keys '%s' in line '%s'" % (e, Arg, list(input_roles_words.keys()), line))
                raise

            input_roles_words2 = dict((r, net.missing_word_id) for r in (roles))
            input_roles_words2[net.role_vocabulary["V"]] = Vrep           
            x_w_i, x_r_i, x_f_i, x_a_i, \
            y_w_i, y_r_i, y_f_i, y_a_i = ( #, bicknell, context, a1  = (
                numpy.asarray([[v for (k,v) in input_roles_words2.items()],], dtype=numpy.int64),         # x_w_i
                numpy.asarray([[k for (k,v) in input_roles_words2.items()],], dtype=numpy.int64),         # x_r_i
                numpy.asarray([[frameRep            for (k,v) in input_roles_words2.items()],], dtype=numpy.int64),         # x_f_i
                numpy.asarray([[net.missing_anim_id for (k,v) in input_roles_words2.items()],], dtype=numpy.int64),         # x_a_i

                numpy.asarray([v for (k,v) in input_roles_words.items() if v !=  net.missing_word_id], dtype=numpy.int64),         # y_w_i
                numpy.asarray([k for (k,v) in input_roles_words.items() if v !=  net.missing_word_id], dtype=numpy.int64),         # y_r_i
                numpy.asarray([net.missing_frame_id for (k,v) in input_roles_words.items() if v !=  net.missing_word_id], dtype=numpy.int64),         # y_f_i
                numpy.asarray([v for (k,v) in input_roles_anims.items() if v !=  net.missing_anim_id], dtype=numpy.int64),         # y_a_i

#                [0.0, ] * len(input_roles_words2),                                                                   # scores
#                "\"" + Arg["A0"] + " " + Arg["V"] + "\"",                                  # context
#                [Arg["V"], ]  * len(input_roles_words2)
            )

            p_pairwise = net.p_words2(x_w_i, x_r_i, x_f_i, x_a_i,
                                      y_w_i, y_r_i, y_f_i, y_a_i)
            
            
        min_p_pair = min(p_pairwise)
        #min_p_pair = max(min_p_pair, pscore)
        min_p_pair = (min_p_pair + pscore) / 2
        p_pair_plaus = (min_p_pair >= config.minPscore)
            
        pplaus = (pscore >= config.minPscore)   # 0.003: acc 64% f 62%; 0.0001: f 74%
#        currSetPScores.append(pscore)
        currSetPScores.append(min_p_pair)
        if print_result:
            print("\t".join( (Arg["ID"], ("(%s)" % Arg["roleset"]), Arg["A0"], Arg["V"], Arg["A1"], Arg["LOC"],Arg["TMP"],Arg["MNR"], Arg["Other"],Arg["UNK"],
                score, str(plausible),
                "%.5f" % pscore, str(pplaus),  ("CORRECT" if (plausible == pplaus) else "INCORRECT"),
                ",".join("%.5f" % p_pair for p_pair in  p_pairwise), "%.5f" % min_p_pair,  ("CORRECT" if (plausible == p_pair_plaus) else "INCORRECT"),
                comment ) ))
#        if pplaus == plausible:
        if  p_pair_plaus == plausible:
            num_correct += 1
#        confusion["gold %s" % plausible][pplaus] += 1
        confusion["gold %s" % plausible][p_pair_plaus] += 1
    data_size = i # if having header line: i-1
    accuracy = float(num_correct)/float(data_size)
    aggr_accuracy = float(aggr_num_correct)/float(aggr_data_size)
    
    if print_result:
        print("results per record (per candidate analysis) :")
        print_scores(data_size, skipped, num_correct, accuracy, confusion)
        print("#na (not a verb): %d; #OOV trigger verb (not in mapping): %d; #verb-frame not in mapping: %d; #Unhandled Unk roles: %d" % (numofNotVerb, numofOOV, numofNoMapping, numofUnhandledUnks))
        print()
        print("aggregated results (per candidate set ; per frame) :")
        print_scores(aggr_data_size, 0, aggr_num_correct, aggr_accuracy, aggr_confusion)
        
        print()
        print("model: %s, eval set: %s, min predicted score threshold: %f" % (model_name,model_and_ver, config.minPscore))
        #print "shdLowercase: %s, shdTruncConjunction: %s, shdRemapOtherArg:%s" % (config.shdLowercase, config.shdTruncConjunction, config.shdRemapOtherArg)
        print("\n".join(sorted([str(i) for i in list(vars(config).items()) if not i[0][:2]=="__"])))
        print(input_config)
        
    net.set_bias(bias)
    return num_correct, data_size, accuracy

def print_scores(data_size, skipped, num_correct, accuracy, confusion ):
        print()
        print("Number of lines %d" % data_size)
        print("Number of lines skipped %d, processed %s" % (skipped, data_size-skipped))
        print("Final score of theano model is %d/%d=%.4f" % (num_correct, data_size, accuracy))
        print("Final score without skipped %d/%d=%.4f" % (num_correct, data_size-skipped,  float(num_correct)/float(data_size-skipped)))
        print("confusion matrix: \n%s" % "\n".join(("{}: {}".format (k,v)) for (k,v) in confusion.items()))
        
        try:
            recall = (float)(confusion["gold %s" % True][True]) / sum(v for v in list(confusion["gold %s" % True].values()))
        except ZeroDivisionError:
            recall = 0.0
        try:
            precis = (float)(confusion["gold %s" % True][True]) / sum(confusion[k][True] for k in list(confusion.keys()))
        except ZeroDivisionError:
            precis = 0.0
        try:
            fscore = 2.0 * precis * recall / (precis + recall)
        except ZeroDivisionError:
            fscore = 0.0
        print("plausible prec: %.2f, recall: %.2f, f: %.2f" % (precis, recall, fscore))

        try:
            recall = (float)(confusion["gold %s" % False][False]) / sum(v for v in list(confusion["gold %s" % False].values()))
        except ZeroDivisionError:
            recall = 0.0
        try:
            precis = (float)(confusion["gold %s" % False][False]) / sum(confusion[k][False] for k in list(confusion.keys()))
        except ZeroDivisionError:
            precis = 0.0
        try:
            fscore = 2.0 * precis * recall / (precis + recall)
        except ZeroDivisionError:
            fscore = 0.0
        print("Implausible prec: %.2f, recall: %.2f, f: %.2f" % (precis, recall, fscore))

        relgains = confusion["gold %s" % False][False] - confusion["gold %s" % True][False]
        print("Relative gains: %d / %d (%.2f%% of %d optimal) (%.2f%% of %d queries)" % (relgains, data_size,
            float(relgains) /  sum(v for v in list(confusion["gold %s" % False].values())) * 100, sum(v for v in list(confusion["gold %s" % False].values())),
            float(relgains) / data_size * 100,   data_size))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        model_name = sys.argv[1]
    else:
        sys.exit("Model name input argument missing missing")
    
    if len(sys.argv) > 2:
        experiment_version = sys.argv[2]
    else:
        sys.exit("Experiment input argument missing missing")

    if len(sys.argv) > 3:
        input_filename = sys.argv[3]
    else:
        input_filename = 'fn-vn-pb-map.out.PBSA'
        
    model_and_ver = model_name + '_' + experiment_version

    eval_a0_v_a1_anim(model_name, model_and_ver, input_filename) 



