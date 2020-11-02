'''
config.py


Author: Tony Hong. Modified by Yuval Marton.


This file should be placed at the dir of the source codes "src/".
Overall structure:
	+ base
	|-- src 	# source code
	|-- corpus 	# labelled corpus (optional, can be put anywhere; set in format_datasets* )
	|-- data 	# featured, formatted data for training, validation and testing
	|-- model 	# trained models
        |-- results     # validation/test results of trained models
'''

import os


'''
Basic configuration
'''
# Base dir
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# src dit
SRC_DIR = os.path.dirname(os.path.abspath(__file__))

# Labelled corpus path
CORPUS_PATH = os.path.join(BASE_DIR, 'corpus/')

# Data path
DATA_PATH = os.path.join(BASE_DIR, 'data/')
DATA_PATH = '/media/data-disk/data/event-rep/exp9_0.1-16-16-Roles2Args3Mods-NoFrAn-v1/'

# data2 path
# DATA2_DIR = os.path.join(BASE_DIR, 'data/')
# DATA2_DIR = '/media/data-disk/data/event-rep'
DATA2_DIR = '/home/yn2373/seq_event-rep/'

# Model path
MODEL_PATH = os.path.join(BASE_DIR, 'model/')
# MODEL_PATH = '/media/data-disk/models'

# Evaluation data path
EVAL_PATH = os.path.join(BASE_DIR, 'eval_data/')

# Data
def getDataVersion(data_version):
    #return os.path.join(DATA_PATH, 'test/')
    return os.path.join(DATA2_DIR, data_version)
#DATA_VERSION = os.path.join(DATA_PATH, 'test/') # 'exp2/') # 'exp3/') # 'test/')
#DATA_VERSION = '/root/home/data/rw-eng/ukwac-proc-out-preproc4DL-20190929/exp1_0.001-2-2-v2/'

# Model
def getModelVersion(model_name):
    return os.path.join(MODEL_PATH, 'test/')
    #return os.path.join(MODEL_PATH, model_name)
MODEL_VERSION = os.path.join(MODEL_PATH, 'test/') # 'exp2/') #'exp3/') #'test/')
#MODEL_VERSION = '/root/home/data/rw-eng/ukwac-proc-out-preproc4DL-20190929/exp1_0.001-2-2-v2/'

# Results path (output of tests)
RESULTS_PATH = os.path.join(BASE_DIR, 'results/')

import subprocess


ANIM_HMN = "Sentient"
ANIM_NE_PERSON = "PERSON"
ANIM_NONE = "None"
ANIMS = {ANIM_NONE: 0, "Animate": 1, ANIM_HMN: 2}


"""
# Semantic role dict
ROLES_SHORT = {
    "A0": 0, 
    "A1": 1, 
    "AM-LOC": 2, 
    "AM-TMP": 3, 
    "AM-MNR": 4, 
    "V": 5,
    "<OTHER>": 6
    }

ROLES = {
    'A0': 5,
    'A1': 1,
    'A2': 4,
    'A3': 10,
    'A4': 14,
    'A5': 28,
    'AM': 25,
    'AM-ADV': 12,
    'AM-CAU': 8,
    'AM-DIR': 18,
    'AM-DIS': 6,
    'AM-EXT': 24,
    'AM-LOC': 2,
    'AM-MNR': 7,
    'AM-MOD': 21,
    'AM-NEG': 13,
    'AM-PNC': 15,
    'AM-PRD': 27,
    'AM-TMP': 3,
    'C-A1': 26,
    'C-V': 9,
    'R-A0': 11,
    'R-A1': 17,
    'R-A2': 20,
    'R-A3': 29,
    'R-AM-CAU': 23,
    'R-AM-LOC': 16,
    'R-AM-MNR': 19,
    'R-AM-TMP': 22,
    '<OTHER>': 30
    }
"""
# TODO: read roles from description file

#ROLE_PRD = "PRD"
#ROLE_OTHER = "ARG-OTHER"
#ROLES = {"ARG0": 0, "ARG1": 1, "ARGM-LOC": 2, "ARGM-TMP": 3, "ARGM-MNR": 4, ROLE_PRD: 5, ROLE_OTHER: 6}
#ROLES_SHORT = ROLES

import roles
ROLES_CLS = roles.Roles2Args3Mods
#TRAIN_ROLES = ROLES_CLS.TRAIN_ROLES
#TEST_ROLES  = ROLES_CLS.TEST_ROLES
#ROLE_PRD    = ROLES_CLS.ROLE_PRD
#ROLE_OTHER  = ROLES_CLS.ROLE_OTHER

'''
Default Training configuration
# Multi-task role filler (MTRF)
'''


# Mini-batch size for NN
BATCH_SIZE = 512 #128 #512  #1024 #2500 #300 #3000


#SAMPLES_EPOCH = 2999374 / 10 # / 100 # 29939975 / 10  #10 * 1000000 #23922262 #10 * 1000000 # 140000 #1000000 #100000000


EPOCHS = 25 # 200


PRINT_AFTER = 10 #5 #1 #10 #100


SAVE_AFTER = 200 #50 #500 #1000 #5000 #2000 # 4000


FACTOR_NUM = 256


HIDDEN_NUM = 512


LOSS_WEIGHT_ROLE = 1.0

LEARNING_RATE = 0.01 #(TEAM2-change) ORIGINAL = 0.1, for ADAM -> change to 0.01
LEARNING_RATE_DECAY = 1.0

L1_REG = 0.00

L2_REG = 0.00

USE_DROPOUT = False
DROPOUT_RATE = 0.2


'''
Data size
Version:
    October 2016
'''
OCT_VALID_SIZE = 1561092
OCT_TEST_SIZE  = 240000 # 1576000



'''
Data size
Version:
    March 2017
'''
# TODO need to compute
MAR_VALID_SIZE = 1561092
MAR_TEST_SIZE = 1576000



'''
Data size
Version:
    Nov 2017 processed , March 2017 version
'''
# TODO need to compute
MAR17_VALID_SIZE = 200000
MAR17_TEST_SIZE = 200000


# exp5-408 files:
# 299722 ../data/exp5-408/NN_dev
# 297778 ../data/exp5-408/NN_test
# 29939975 ../data/exp5-408/NN_train
EXP5_408_VALID_SIZE = 299722 / 10
EXP5_408_TEST_SIZE  = 297778 


# exp6-48 files:
#  299722 ../data/test/NN_dev
#  297778 ../data/test/NN_test
# 2999374 ../data/test/NN_train
EXP6_48_VALID_SIZE = 299722 / 2
EXP6_48_TEST_SIZE  = 297778

# ukwac-proc-out-preproc4DL-20190929$ wc -l exp1_0.01-4-4/
#  318482 exp1_0.01-4-4/NN_dev
#   313730 exp1_0.01-4-4/NN_test
#  2708494 exp1_0.01-4-4/NN_train
EXP1_20190929_VALID_SIZE = 2708494 
EXP1_20190929_TEST_SIZE  = 313730


# data sizes to be used now:
#VALID_SIZE = EXP1_20190929_VALID_SIZE # = 1561092
#TEST_SIZE  = EXP1_20190929_TEST_SIZE  #= 240000 # 1576000   

def getValidationSetSize(data_version):
    ret_val, VALID_SIZE = subprocess.getstatusoutput("wc -l  \"%s/%s/NN_dev\"" % (DATA2_DIR, data_version))
    print ("VALID_SIZE: %s, ret_val: %s" % (VALID_SIZE, ret_val))
    return int(VALID_SIZE.split()[0])
def getTestSetSize(data_version):
    ret_val, TEST_SIZE  = subprocess.getstatusoutput("wc -l  \"%s/%s/NN_test\"" % (DATA2_DIR, data_version))
    print ("TEST_SIZE: %sm ret_val: %s" % (TEST_SIZE, ret_val))
    return int(TEST_SIZE.split()[0])

def getTrainingSetSize(data_version):
    ret_val, TRAIN_SIZE = subprocess.getstatusoutput("wc -l  \"%s/%s/NN_train\"" % (DATA2_DIR, data_version))
    print ("TRAIN_SIZE: %s, ret_val: %s" % (TRAIN_SIZE, ret_val))
    return int(TRAIN_SIZE.split()[0])
#def getSampleEpochs(data_version):
#    return getTrainingSetSize(data_version) / 10
##    return getValidationSetSize(data_version) / 10
##SAMPLES_EPOCH = VALID_SIZE / 10 # / 100 # 29939975 / 10  #10 * 1000000 #23922262 #10 * 1000000 # 140000 #1000000 #100000000


'''
# RNN
'''
# Mini-batch size for RNN
BATCH_SIZE_RNN = 128



'''
Evaluation configuration
'''
### *** Important ***
#   This option is for evaluation of Semantic Role Classification where semantic role is not given for each input word.
#   Do not set this to True during the training! 
# SRC = True
SRC = False

