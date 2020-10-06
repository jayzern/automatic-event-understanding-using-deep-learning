''' This is a module containing methods for creating mini-batches.
    
    Author: Tony Hong

    Ref: Ottokar Tilk, Event participant modelling with neural networks, EMNLP 2016
'''

import os, re
from collections import OrderedDict


import numpy as np
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.utils import to_categorical


def random_lines(f, file_length, batch_size, rng, max_line_len=372):
    """
    batch_size consecutive lines from a random position in file
    """
    while True:
        offset = rng.randint(0, file_length - max_line_len * (batch_size + 2))
        f.seek(offset)
        chunk = f.read(max_line_len * (batch_size + 2))
        for line in chunk.split(os.linesep)[1:1+batch_size]:
            yield line


def get_NN_batch(x_w_i, x_r_i, x_f_i, x_a_i,
                 y_w_i, y_r_i, y_f_i, y_a_i):
    return ([
        np.asarray(x_w_i, dtype=np.int32),
        np.asarray(x_r_i, dtype=np.int32),
        np.asarray(x_f_i, dtype=np.int32),
        np.asarray(x_a_i, dtype=np.int32),
        
        np.asarray(y_r_i, dtype=np.int32),

    ],
    [
        np.asarray(y_w_i, dtype=np.int32),
#        np.asarray(y_f_i, dtype=np.int32),
#        np.asarray(y_a_i, dtype=np.int32),
    ])

def get_MT_batch(x_w_i, x_r_i, x_f_i, x_a_i,
                 y_w_i, y_r_i, y_f_i, y_a_i):
    return ([
        np.asarray(x_w_i, dtype=np.int32),
        np.asarray(x_r_i, dtype=np.int32),
        np.asarray(x_f_i, dtype=np.int32),
        np.asarray(x_a_i, dtype=np.int32),
        
        np.asarray(y_w_i, dtype=np.int32),
        np.asarray(y_r_i, dtype=np.int32),
#        np.asarray(y_f_i, dtype=np.int32),
#        np.asarray(y_a_i, dtype=np.int32),
        
    ],
    [
        np.asarray(y_w_i, dtype=np.int32),
        np.asarray(y_r_i, dtype=np.int32),
#        np.asarray(y_f_i, dtype=np.int32),
#        np.asarray(y_a_i, dtype=np.int32),
    ])



def generator(file_name, model_name,
              unk_word_id, unk_role_id, unk_frame_id,     unk_anim_id,
              missing_word_id,          missing_frame_id, missing_anim_id,
              n_roles,
              random=False, rng=None, batch_size=0, neg=0, aligned=False):
    """Generates k noise samples for target role + 1 positive sample from data. Noise and positive samples share inputs"""

    if re.search('NNRF', model_name):
        get_batch = get_NN_batch
    else:
        get_batch = get_MT_batch

    while True:
        with open(file_name, 'r') as f:

            if random:
                file_length = os.stat(file_name).st_size
                lines = random_lines(f, file_length, batch_size, rng)
            else:
                lines = f

            x_w_i = []
            x_r_i = []
            x_f_i = []
            x_a_i = []
            
            y_w_i = []
            y_r_i = []
            y_f_i = []
            y_a_i = []
            
            n_total_samples = 0
            n_neg_samples = 0

            for line in lines:
                d = eval(line)
                roles, words_anims_frames = map(list, zip(*d.items()))
                words, anims, frames =map(list, zip( *words_anims_frames))   # till now words was a tuple: (word, anim, frame)

                # non_missing_inputs = [i for i, r in enumerate(roles) if words[i] != missing_word_id and r not in [5, 6]]
                non_missing_inputs = [i for i, r in enumerate(roles) if words[i] != missing_word_id]

                # Generate samples for each given (non-missing-word) role-word pair
                for i in non_missing_inputs:

                    # Positive sample

                    # Remove current role-word pair from context ...
                    input_words = words[:]
                    input_roles = roles[:]
                    input_frames = frames[:]
                    input_anims = anims[:]
                      

                    if not aligned:
                        del input_words[i]
                        del input_roles[i]
                        del input_frames[i]
                        del input_anims[i]
                    else:
                        input_words[i] = missing_word_id
                        input_frames[i] = missing_frame_id
                        input_anims[i] = missing_anim_id
                        

                    # ... and set it as target
                    target_word = words[i]
                    target_role = roles[i]
                    target_frame =frames[i]
                    target_anim = anims[i]


                    target_words = [target_word]
                    target_roles = [target_role]
                    target_frames= [target_frame]
                    target_anims = [target_anim]

                    x_w_i.append(input_words)
                    x_r_i.append(input_roles)
                    x_f_i.append(input_frames)
                    x_a_i.append(input_anims)
                    
                    n_total_samples += 1
                    
                    # generate k negative samples by corrupting one non missing input role
                    for _ in range(neg):

                        noise_role = target_role
                        noise_word = target_word
                        while noise_word == target_word:
                            noise_word = np.random.randint(missing_word_id) # missing_word_id == len(real vocabulary)
                        #noise_word = np.random.choice(word_ids, p=unigram_counts[noise_role])
                        noise_frame = target_frame
                        while noise_frame == target_frame:
                            noise_frame = np.random.randint(missing_frame_id) 
                        noise_anim = target_anim
                        while noise_anim == target_anim:
                            noise_anim = np.random.randint(missing_anim_id)
                            
                        target_words.append(noise_word)
                        target_roles.append(noise_role)
                        target_frames.append(noise_frame)
                        target_anims.append(noise_anim)
                        

                        n_neg_samples += 1
                        n_total_samples += 1
                        
                    y_w_i.append(target_words)
                    y_r_i.append(target_roles)
                    y_f_i.append(target_frames)
                    y_a_i.append(target_anims)
                    

                    if len(x_w_i) >= batch_size:
                        # print x_w_i[-1]
                        # print (os.getpid(), x_w_i[batch_size-1])

                        # print x_w_i
                        # print x_r_i
                        # print y_w_i
                        # print y_r_i

                        yield (get_batch(x_w_i, x_r_i, x_f_i, x_a_i,
                                         y_w_i, y_r_i, y_f_i, y_a_i))

                        x_w_i = []
                        x_r_i = []
                        x_f_i = []
                        x_a_i = []
                        
                        y_w_i = []
                        y_r_i = []
                        y_f_i = []
                        y_a_i = []
                        
                        n_total_samples = 0
                        n_neg_samples = 0
#            # end of file reached (Yuval added)
#            yield (get_batch(x_w_i, x_r_i, x_f_i, x_a_i,
#                             y_w_i, y_r_i, y_f_i, y_a_i))
                                                                                                                                                                                     


def get_minibatch(file_name,
                  unk_word_id, unk_role_id, unk_frame_id,     unk_anim_id,
                  missing_word_id,          missing_frame_id, missing_anim_id,
                  n_roles,
                  random=False, rng=None, batch_size=0, neg=0):
    """Generates k noise samples for target role + 1 positive sample from data. Noise and positive samples share inputs"""

    #word_ids = np.arange(len(unigram_counts[0])).astype(np.float32)

    with open(file_name, 'r') as f:

        if random:
            file_length = os.stat(file_name).st_size
            lines = random_lines(f, file_length, batch_size, rng)
        else:
            lines = f

        x_w_i = []
        x_r_i = []
        x_f_i = []
        x_a_i = []
        
        y_w_i = []
        y_r_i = []
        y_f_i = []
        y_a_i = []
        
        n_total_samples = 0
        n_neg_samples = 0

        for line in lines:
            d = eval(line)
            #roles, words = map(list, zip(*d.items()))
            roles, words_anims_frames = map(list, zip(*d.items()))
            words, anims, frames =map(list, zip( *words_anims_frames))   # till now words was a tuple: (word, anim, frame)
            
            non_missing_inputs = [i for i, r in enumerate(roles) if words[i] != missing_word_id]

            # Generate samples for each given (non-missing-word) role-word pair
            for i in non_missing_inputs:

                # Positive sample

                # Remove current role-word pair from context ...
                input_words = words[:]
                input_roles = roles[:]
                input_frames = frames[:]
                input_anims = anims[:]
                
                del input_words[i]
                del input_roles[i]
                del input_frames[i]
                del input_anims[i]        
                    
                # ... and set it as target
                target_word = words[i]
                target_role = roles[i]
                target_frame =frames[i]
                target_anim = anims[i]
                                
                target_words = [target_word]
                target_roles = [target_role]
                target_frames= [target_frame]
                target_anims = [target_anim]
                
                x_w_i.append(input_words)
                x_r_i.append(input_roles)
                x_f_i.append(input_frames)
                x_a_i.append(input_anims)
                
                n_total_samples += 1                                                                                                                                                                                                                             
                
                # generate k negative samples by corrupting one non missing input role
                for _ in range(neg):

                    noise_role = target_role
                    noise_word = target_word
                    while noise_word == target_word:
                        noise_word = np.random.randint(missing_word_id) # missing_word_id == len(real vocabulary)
                    #noise_word = np.random.choice(word_ids, p=unigram_counts[noise_role])
                    noise_frame = target_frame
                    while noise_frame == target_frame:
                        noise_frame = np.random.randint(missing_frame_id)
                    noise_anim = target_anim
                    while noise_anim == target_anim:
                        noise_anim = np.random.randint(missing_anim_id)
                        
                    target_words.append(noise_word)
                    target_roles.append(noise_role)
                    target_frames.append(noise_frame)
                    target_anims.append(noise_anim)
                    
                    n_neg_samples += 1
                    n_total_samples += 1
                    
                y_w_i.append(target_words)
                y_r_i.append(target_roles)
                y_f_i.append(target_frames)
                y_a_i.append(target_anims)
                                     
                if len(x_w_i) >= batch_size:

                    yield ([
                        np.asarray(x_w_i, dtype=np.int32),
                        np.asarray(x_r_i, dtype=np.int32),
                        np.asarray(x_f_i, dtype=np.int32),
                        np.asarray(x_a_i, dtype=np.int32),
                        
                        np.asarray(y_w_i, dtype=np.int32),
                        np.asarray(y_r_i, dtype=np.int32),
                        np.asarray(y_f_i, dtype=np.int32),
                        np.asarray(y_a_i, dtype=np.int32),
                    ],
                    [
                        np.asarray(to_categorical(y_w_i, missing_word_id+2), dtype=np.int32),
                        np.asarray(to_categorical(y_r_i, n_roles), dtype=np.int32),
                        np.asarray(to_categorical(y_f_i, n_roles), dtype=np.int32),
                        np.asarray(to_categorical(y_a_i, n_roles), dtype=np.int32),
                    ], )

                    x_w_i = []
                    x_r_i = []
                    x_f_i = []
                    x_a_i = []
                                                            
                    y_w_i = []
                    y_r_i = []
                    y_f_i = []
                    y_a_i = []
                                                            
                    n_total_samples = 0
                    n_neg_samples = 0
