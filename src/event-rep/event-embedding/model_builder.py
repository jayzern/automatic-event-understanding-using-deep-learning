# model_builder.py
import re
import os
import pickle as cPickle

from model import *

def load_description(file_dir, model_name):
        description_file = os.path.join(file_dir, model_name + "_description")        

        with open(description_file, 'rb') as f:
            try:
                description = cPickle.load(f)
            except UnicodeDecodeError:
                f.seek(0)
                description = cPickle.load(f, encoding='latin1')
                
        return description

def build_model(model_name, description):
    if re.search('NNRF', model_name):
        net = NNRF(
            n_word_vocab = len(description["word_vocabulary"]),
            n_role_vocab = len(description["role_vocabulary"]),
            n_factors_emb = description["n_factors_emb"],
            n_hidden = description["n_hidden"],
            word_vocabulary = description["word_vocabulary"],
            role_vocabulary = description["role_vocabulary"],
            unk_word_id = description["unk_word_id"],
            unk_role_id = description["unk_role_id"],
            missing_word_id = description["missing_word_id"],
            using_dropout = description["using_dropout"],
            dropout_rate = description["dropout_rate"]
            )
    elif "frame_vocabulary" in description:
        net = eval(model_name)(
#                n_word_vocab = len(description["word_vocabulary"]),
#                n_role_vocab = len(description["role_vocabulary"]),
#                n_frame_vocab= len(description["frame_vocabulary"]),
#                n_anim_vocab = len(description["anim_vocabulary"]),
                
#                n_factors_emb = description["n_factors_emb"],
                
                n_hidden = description["n_hidden"],
                using_dropout = description["using_dropout"],
                dropout_rate = description["dropout_rate"],
                
                word_vocabulary = description["word_vocabulary"],
                role_vocabulary = description["role_vocabulary"],
                unk_word_id = description["unk_word_id"],
                unk_role_id = description["unk_role_id"],
                missing_word_id = description["missing_word_id"],
                missing_role_id = description["missing_word_id"],  # not really needed

                n_factors_emb_word = description["n_factors_emb_word"],
                n_factors_emb_role = description["n_factors_emb_role"],
                n_factors_emb_frame= description["n_factors_emb_frame"],
                n_factors_emb_anim = description["n_factors_emb_anim"],

                frame_vocabulary= description["frame_vocabulary"],
                anim_vocabulary = description["anim_vocabulary"],               
                unk_frame_id= description["unk_frame_id"],
                unk_anim_id = description["unk_anim_id"],
                missing_frame_id= description["missing_frame_id"],
                missing_anim_id = description["missing_anim_id"]            
            )
    else:
        net = eval(model_name)(
                n_word_vocab = len(description["word_vocabulary"]),
                n_role_vocab = len(description["role_vocabulary"]),
#                n_frame_vocab= len(description["frame_vocabulary"]),
#                n_anim_vocab = len(description["anim_vocabulary"]),
                
                n_factors_emb = description["n_factors_emb"],
                
                n_hidden = description["n_hidden"],
                using_dropout = description["using_dropout"],
                dropout_rate = description["dropout_rate"],
                
                word_vocabulary = description["word_vocabulary"],
                role_vocabulary = description["role_vocabulary"],
                unk_word_id = description["unk_word_id"],
                unk_role_id = description["unk_role_id"],
                missing_word_id = description["missing_word_id"],
 #               missing_role_id = description["missing_word_id"]  # not really needed

 #               n_factors_emb_word = description["n_factors_emb_word"],
 #               n_factors_emb_role = description["n_factors_emb_role"],             
            )                

    return net
