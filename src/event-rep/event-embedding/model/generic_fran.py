''' This module contains generic model of role-fillering with animacy/sentience and FrameNet frame info.

    Author: Yuval Marton (Based on code by Tony Hong)
'''
import os
import re
import pickle

from tensorflow.keras.models import load_model

import config
from utils import get_reverse_map


class GenericFrAnModel(object):
    """ Generic model for role filler with semantic Frames and Animacy info
    """
    def __init__(self,
                 n_hidden=300,
                 n_factors_emb_word=300,n_factors_emb_role=8,n_factors_emb_frame=300,n_factors_emb_anim=300,
                 word_vocabulary=None, role_vocabulary=None, frame_vocabulary=None, anim_vocabulary=None,
                 unk_word_id=50000,    unk_role_id=7,        unk_frame_id=-1,       unk_anim_id=3,
                 missing_word_id=50001,missing_role_id=None, missing_frame_id=-2,   missing_anim_id=4,
                 using_dropout=False, dropout_rate=0.3, optimizer='adagrad', loss='sparse_categorical_crossentropy',
                 metrics=['accuracy'], loss_weights=[1., 1.]):
#                 n_word_vocab, n_role_vocab, n_factors_emb, n_hidden, word_vocabulary, role_vocabulary, 
#        unk_word_id, unk_role_id, missing_word_id, using_dropout, dropout_rate, optimizer, loss, metrics):

        self.n_word_vocab = len(word_vocabulary) # n_word_vocab
        self.n_role_vocab = len(role_vocabulary)

        if (frame_vocabulary is None) or (len(frame_vocabulary) < 3):
            self.n_frame_vocab = None
            self.n_anim_vocab = None
            self.frame_vocabulary = None
            self.anim_vocabulary = None
        else:
            self.n_frame_vocab = len(frame_vocabulary)
            self.n_anim_vocab = len(anim_vocabulary)
            self.n_factors_emb_frame = n_factors_emb_frame
            self.n_factors_emb_anim = n_factors_emb_anim
            self.frame_vocabulary = frame_vocabulary
            self.anim_vocabulary = anim_vocabulary
            self.frame_decoder = get_reverse_map(frame_vocabulary)
            self.anim_decoder = get_reverse_map(anim_vocabulary)
            self.unk_frame_id = unk_frame_id
            self.unk_anim_id = unk_anim_id
            self.missing_frame_id= missing_frame_id
            self.missing_anim_id = missing_anim_id
        
        self.n_factors_emb_word = n_factors_emb_word
        self.n_factors_emb_role = n_factors_emb_role
        
        self.n_hidden = n_hidden

        self.word_vocabulary = word_vocabulary
        self.role_vocabulary = role_vocabulary
        
        self.word_decoder = get_reverse_map(word_vocabulary)
        self.role_decoder = get_reverse_map(role_vocabulary)
        
        self.unk_role_id = unk_role_id
        self.unk_word_id = unk_word_id
        
        self.missing_word_id = missing_word_id
        self.missing_role_id = missing_role_id

        self.using_dropout = using_dropout
        self.dropout_rate = dropout_rate
        self.optimizer = optimizer
        self.loss = loss

        # assert missing_word_id == len(word_vocabulary)
        # assert unk_word_id == len(word_vocabulary) + 1
        # assert unk_role_id == len(role_vocabulary)
        
    def save(self, file_dir, file_name, model_name,
             learning_rate=None,learning_rate_decay=None,
             validation_cost_history=None, best_validation_cost=None,
             best_epoch=None, epoch=None):
        ''' Save current model
        '''
        description_file = os.path.join(file_dir, file_name + "_description")
        model_file = os.path.join(file_dir, file_name + '.h5')

        if self.frame_vocabulary:
            description = {
                "n_word_vocab":             self.n_word_vocab,
                "n_role_vocab":             self.n_role_vocab,
                "n_frame_vocab":            self.n_frame_vocab,
                "n_anim_vocab":             self.n_anim_vocab,

                "n_factors_emb_word":            self.n_factors_emb_word,
                "n_factors_emb_role":            self.n_factors_emb_role,
                "n_factors_emb_frame":           self.n_factors_emb_frame,
                "n_factors_emb_anim":            self.n_factors_emb_anim,

                "n_hidden":                 self.n_hidden,

                "word_vocabulary":          self.word_vocabulary,
                "role_vocabulary":          self.role_vocabulary,
                "frame_vocabulary":         self.frame_vocabulary,
                "anim_vocabulary":          self.anim_vocabulary,

                "unk_role_id":              self.unk_role_id,
                "unk_word_id":              self.unk_word_id,
                "unk_frame_id":             self.unk_frame_id,
                "unk_anim_id":              self.unk_anim_id,

                "missing_word_id":          self.missing_word_id,
                "missing_role_id":          self.missing_role_id,
                "missing_frame_id":         self.missing_frame_id,
                "missing_anim_id":          self.missing_anim_id,

                "using_dropout":            self.using_dropout,
                "dropout_rate":             self.dropout_rate,

                "learning_rate":            learning_rate,
                "learning_rate_decay":      learning_rate_decay,

                "validation_cost_history":  validation_cost_history,
                "best_validation_cost":     best_validation_cost,
                "best_epoch":               best_epoch,
                "epoch":                    epoch,
            }
        else: # no frames or anim
            description = {
                "n_word_vocab":             self.n_word_vocab,
                "n_role_vocab":             self.n_role_vocab,

                "n_factors_emb_word":            self.n_factors_emb_word,
                "n_factors_emb_role":            self.n_factors_emb_role,

                "n_hidden":                 self.n_hidden,

                "word_vocabulary":          self.word_vocabulary,
                "role_vocabulary":          self.role_vocabulary,

                "unk_role_id":              self.unk_role_id,
                "unk_word_id":              self.unk_word_id,

                "missing_word_id":          self.missing_word_id,
                "missing_role_id":          self.missing_role_id,

                "using_dropout":            self.using_dropout,
                "dropout_rate":             self.dropout_rate,

                "learning_rate":            learning_rate,
                "learning_rate_decay":      learning_rate_decay,

                "validation_cost_history":  validation_cost_history,
                "best_validation_cost":     best_validation_cost,
                "best_epoch":               best_epoch,
                "epoch":                    epoch,
            }
        
        with open(description_file, 'wb') as f:
            pickle.dump(description, f, protocol=pickle.HIGHEST_PROTOCOL)

        if re.search('final', file_name) or re.search('A2', file_name):
            self.model.save_weights(model_file)
        else:
            self.model.save(model_file)


    def load(self, file_dir, file_name, description):
        """ Load model from description
        """
        model_file = os.path.join(file_dir, file_name + '.h5')

        try:
            learning_rate        = description["learning_rate"]
            learning_rate_decay  = description["learning_rate_decay"]
            validation_cost_history = description["validation_cost_history"]
            best_validation_cost    = description["best_validation_cost"]
            best_epoch = description["best_epoch"]
            epoch      = description["epoch"]
        except Exception as e:
            print(("ERROR: missing key in description file: %s\n" % e))
            raise
        finally:
            print(("description file preview:\n%s\n" % \
                 "\n".join("%s: %s..." % (k,str(v)[:64]) for (k,v) in sorted(description.items()))))

        if config.SRC:
            print(("Load model directly for: ", file_name))
            self.model = load_model(model_file)
        else:
            print(("Load weights only for: ", file_name))
            self.model.load_weights(model_file)

        return learning_rate, learning_rate_decay, validation_cost_history, best_validation_cost, best_epoch, epoch
        
