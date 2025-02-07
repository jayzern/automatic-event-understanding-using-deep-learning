''' This module contains multi-task non-incremental role-filler.

    Author: Tony Hong
    Version: 4
    Ref: Ottokar Tilk, Event participant modelling with neural networks, EMNLP 2016
'''

import numpy as np
from tensorflow.keras import backend as K
from tensorflow.keras.layers import Input, Embedding, Dropout, Dense, Lambda, Add, Multiply, multiply, Masking, Concatenate
from tensorflow.keras.initializers import glorot_uniform
from tensorflow.keras.layers import PReLU
from tensorflow.keras.models import Model, load_model

from .embeddings import factored_embedding
from .layers import target_word_hidden, target_role_hidden
#from generic import GenericModel
from .generic_fran import GenericFrAnModel
from .custom_acc import custom_acc


#class MTRFwFAv1Res(GenericModel):
class MTRFwFAv1Res(GenericFrAnModel):
    """Multi-task non-incremental role-filler with FrameNet frames and sentience/animacy tags for args
       v1
    """
    
    def __init__(self, #n_word_vocab=50001, n_role_vocab=7,
                 n_hidden=300,
                 n_factors_emb_word=256,n_factors_emb_role=300,n_factors_emb_frame=36,n_factors_emb_anim=8,
                 word_vocabulary=None, role_vocabulary=None, frame_vocabulary=None, anim_vocabulary=None,
                 unk_word_id=50000,    unk_role_id=7,        unk_frame_id=-1,       unk_anim_id=3,
                 missing_word_id=50001,missing_role_id=None, missing_frame_id=-2,   missing_anim_id=4,
                 using_dropout=False, dropout_rate=0.3, optimizer='adagrad', loss='sparse_categorical_crossentropy',
                 metrics=['accuracy'], loss_weights=[1., 1.]):
        
        n_word_vocab = len(word_vocabulary) 
        n_role_vocab = len(role_vocabulary)
        n_frame_vocab= len(frame_vocabulary)
        n_anim_vocab = len(anim_vocabulary)
        """
        if (n_word_vocab is not None) and (n_word_vocab >= 0) and (missing_word_id < len(word_vocabulary)):
            n_word_vocab -= 1
        if (n_role_vocab is not None) and (n_role_vocab >= 0) and (missing_role_id < len(role_vocabulary)):
            n_role_vocab -= 1
        if (n_frame_vocab is not None) and (n_frame_vocab >= 0) and (missing_frame_id < len(frame_vocabulary)):
            n_frame_vocab -= 1
        if (n_anim_vocab is not None) and (n_anim_vocab >= 0) and (missing_anim_id < len(anim_vocabulary)):
            n_anim_vocab -= 1
        """
        
        super(MTRFwFAv1Res, self).__init__( #n_word_vocab, n_role_vocab,
            n_hidden,
            n_factors_emb_word,n_factors_emb_role,n_factors_emb_frame,n_factors_emb_anim,
            word_vocabulary, role_vocabulary, frame_vocabulary, anim_vocabulary,
            unk_word_id,     unk_role_id,     unk_frame_id,     unk_anim_id,
            missing_word_id, missing_role_id, missing_frame_id, missing_anim_id,
            using_dropout, dropout_rate, optimizer, loss, metrics)

        assert (n_factors_emb_role == n_factors_emb_word + n_factors_emb_frame + n_factors_emb_anim)
        n_factors_emb = n_factors_emb_role
        
        # minus 1 here because one of the roles is the target (i.e., to be predicted, not in input)
        input_length = n_role_vocab - 1

        n_factors_cls = n_hidden

        # each input is a fixed window of frame set, each word correspond to one role
        input_words = Input(shape=(input_length, ), dtype='int32', name='input_words')
        input_roles = Input(shape=(input_length, ), dtype='int32', name='input_roles')
        input_frames = Input(shape=(input_length, ), dtype='int32', name='input_frames')
        input_anims  = Input(shape=(input_length, ), dtype='int32', name='input_anims')
        
        target_word = Input(shape=(1, ), dtype='int32', name='target_word')
        target_role = Input(shape=(1, ), dtype='int32', name='target_role')
#        target_frame = Input(shape=(1, ), dtype='int32', name='target_frame')
#        target_anim  = Input(shape=(1, ), dtype='int32', name='target_anim')
        
        emb_init = glorot_uniform()
        
        # word embedding; shape is (batch_size, input_length, n_factors_emb)
        word_embedding = Embedding(n_word_vocab, n_factors_emb_word, 
            embeddings_initializer=emb_init,
            name='org_word_embedding')(input_words)
        if n_factors_emb_frame > 0:
            frame_embedding = Embedding(n_frame_vocab, n_factors_emb_frame,
                                    embeddings_initializer=emb_init,
                                    name='org_frame_embedding')(input_frames)
        if n_factors_emb_anim > 0:
            anim_embedding = Embedding(n_anim_vocab, n_factors_emb_anim,
                                   embeddings_initializer=emb_init,
                                   name='org_anim_embedding')(input_anims)

        
#        word_anim_frame_embedding = Concatenate(name='word_anim_frame_embedding')([word_embedding, frame_embedding, anim_embedding])
                                          
            
        # masked word embedding: a hack zeros out the missing word inputs
        weights = np.ones((n_word_vocab, n_factors_emb_word))
        weights[missing_word_id] = 0
        mask = Embedding(n_word_vocab, n_factors_emb_word, 
            weights=[weights], 
            trainable=False,
            name='word_mask')(input_words)
        word_embedding = Multiply(name='word_embedding')([word_embedding, mask])
        emb_combo = [word_embedding,]
        
        # masked frame embedding: a hack zeros out the missing inputs
        if n_factors_emb_frame > 0:
            weights = np.ones((n_frame_vocab, n_factors_emb_frame))
            weights[missing_frame_id] = 0
            mask = Embedding(n_frame_vocab, n_factors_emb_frame,
                             weights=[weights],
                             trainable=False,
                             name='frame_mask')(input_frames)
            frame_embedding = Multiply(name='frame_embedding')([frame_embedding, mask])
            emb_combo.append(frame_embedding)
        
        # masked anim embedding: a hack zeros out the missing inputs
        if n_factors_emb_anim > 0:
            weights = np.ones((n_anim_vocab, n_factors_emb_anim))
            weights[missing_anim_id] = 0
            mask = Embedding(n_anim_vocab, n_factors_emb_anim,
                             weights=[weights],
                             trainable=False,
                             name='anim_mask')(input_anims)
            anim_embedding = Multiply(name='anim_embedding')([anim_embedding, mask])
            emb_combo.append(anim_embedding)                                                              

        # combine word,frame,animacy/sentience
        word_embedding = Concatenate(name='word_anim_frame_embedding')(emb_combo)
#        word_embedding = Concatenate(name='word_anim_frame_embedding')([word_embedding, frame_embedding, anim_embedding])

        
        # role embedding; shape is (batch_size, input_length, n_factors_emb)
        role_embedding = Embedding(n_role_vocab, n_factors_emb_role, 
            embeddings_initializer=emb_init,
            name='role_embedding')(input_roles)

        if using_dropout:
            # Drop-out layer after embeddings
            word_embedding = Dropout(dropout_rate)(word_embedding)
            role_embedding = Dropout(dropout_rate)(role_embedding)

        # hidden units after combining 2 embeddings; shape is the same with embedding
        product = Multiply()([word_embedding, role_embedding])
        #product = Multiply()([role_embedding, word_embedding])
        #product = multiply([role_embedding, word_embedding])

        # fully connected layer, output shape is (batch_size, input_length, n_hidden)
        lin_proj = Dense(n_factors_emb, 
            activation='linear', 
            use_bias=False,
            input_shape=(n_factors_emb,), 
            name='lin_proj')(product)

        non_lin = PReLU(
            alpha_initializer='ones',
            name='non_lin')(lin_proj)
        
        # fully connected layer, output shape is (batch_size, input_length, n_hidden)
        lin_proj2 = Dense(n_factors_emb, 
            activation='linear', 
            use_bias=False,
            input_shape=(n_factors_emb,), 
            name='lin_proj2')(non_lin)

        residual_0 = Add(name='residual_0')([product, lin_proj2])

        # mean on input_length direction;
        # obtaining context embedding layer, shape is (batch_size, n_hidden)
        context_embedding = Lambda(lambda x: K.mean(x, axis=1), 
            name='context_embedding',
            output_shape=(n_factors_emb_word  + n_factors_emb_frame + n_factors_emb_anim ,))(residual_0)  # word+frame+anim ?

        # target word hidden layer
        tw_hidden = target_word_hidden(context_embedding, target_role, n_word_vocab, n_role_vocab, glorot_uniform(), n_hidden, n_hidden)

        # target role hidden layer
        tr_hidden = target_role_hidden(context_embedding, target_word, n_word_vocab, n_role_vocab, glorot_uniform(), n_hidden, n_hidden, 
            using_dropout=using_dropout, dropout_rate=dropout_rate)

#        # target frame hidden layer
#        tf_hidden = target_frame_hidden(context_embedding, target_word, n_word_vocab, n_role_vocab, glorot_uniform(), n_hidden, n_hidden,
#                                       using_dropout=using_dropout, dropout_rate=dropout_rate)
                        
        # softmax output layer
        target_word_output = Dense(n_word_vocab - 1,  # not predicting missing_word_id ever 
            activation='softmax', 
            input_shape=(n_hidden, ), 
            name='softmax_word_output')(tw_hidden)

        # softmax output layer
        target_role_output = Dense(n_role_vocab, 
            activation='softmax', 
            input_shape=(n_hidden, ), 
            name='softmax_role_output')(tr_hidden)

        self.model = Model(inputs=[input_words, input_roles, input_frames, input_anims,
                                   target_word, target_role, ], #target_frame, target_anim],
#                           outputs=[target_word_output, target_role_output, target_frame, target_anim])
                           outputs=[target_word_output, target_role_output])
        # TODO: add targret frame? anim?

        self.model.compile(optimizer, loss, metrics, loss_weights)


        self.dummy_word_np =  np.asarray([missing_word_id] * (n_role_vocab-1), dtype=np.int64).reshape (1, n_role_vocab-1)
        self.dummy_role_np =  np.asarray([missing_role_id] * (n_role_vocab-1), dtype=np.int64).reshape (1, n_role_vocab-1)
        self.dummy_frame_np=  np.asarray([missing_frame_id]* (n_role_vocab-1), dtype=np.int64).reshape (1, n_role_vocab-1)
        self.dummy_anim_np =  np.asarray([missing_anim_id] * (n_role_vocab-1), dtype=np.int64).reshape (1, n_role_vocab-1)
#        self.dummy_word_np =  np.asarray([missing_word_id] * (n_word_vocab-1), dtype=np.int64).reshape (1, n_word_vocab-1)
#        self.dummy_role_np =  np.asarray([missing_role_id] * (n_role_vocab-1), dtype=np.int64).reshape (1, n_role_vocab-1)
#        self.dummy_frame_np=  np.asarray([missing_frame_id]* (n_frame_vocab-1), dtype=np.int64).reshape (1, n_role_vocab-1)
#        self.dummy_anim_np =  np.asarray([missing_anim_id] * (n_anim_vocab-1), dtype=np.int64).reshape (1, n_role_vocab-1)        
        self.t_w_dummy =  np.asarray([missing_word_id] , dtype=np.int64)
        self.t_r_dummy =  np.asarray([missing_role_id] , dtype=np.int64)
    

    def set_0_bias(self):
        word_output_weights = self.model.get_layer("softmax_word_output").get_weights()
        word_output_kernel = word_output_weights[0]
        word_output_bias = np.zeros(self.n_word_vocab - 1) # never predicting missing_word_id
        self.model.get_layer("softmax_word_output").set_weights([word_output_kernel, word_output_bias])

        role_output_weights = self.model.get_layer("softmax_role_output").get_weights()
        role_output_kernel = role_output_weights[0]
        role_output_bias = np.zeros(self.n_role_vocab)
        self.model.get_layer("softmax_role_output").set_weights([role_output_kernel, role_output_bias])

        return word_output_weights[1], role_output_weights[1]


    def set_bias(self, bias):
        word_output_weights = self.model.get_layer("softmax_word_output").get_weights()
        word_output_kernel = word_output_weights[0]
        self.model.get_layer("softmax_word_output").set_weights([word_output_kernel, bias[0]])

        role_output_weights = self.model.get_layer("softmax_role_output").get_weights()
        role_output_kernel = role_output_weights[0]
        self.model.get_layer("softmax_role_output").set_weights([role_output_kernel, bias[1]])

        return bias
        

    # Train and test
    # Deprecated temporarily
    def train(self,
              i_w, i_r, i_f, i_a,
              t_w, t_r, t_f, t_a,
              t_w_c, t_r_c,
              batch_size=256, epochs=100, validation_split=0.05, verbose=0):
        train_result = self.model.fit(
            [
                i_w, i_r, i_f, i_a,
                t_w, t_r, t_f, t_a
            ],
            [
                t_w_c, t_r_c
            ],
            batch_size, epochs, validation_split, verbose)
        return train_result

    def test(self,
             i_w, i_r, i_f, i_a,
             t_w, t_r, t_f, t_a,
             t_w_c, t_r_c,
             batch_size=256, verbose=0):
        test_result = self.model.evaluate(
            [
                i_w, i_r, i_f, i_a,
                t_w, t_r, t_f, t_a,
            ], [
                t_w_c, t_r_c
            ],
            batch_size, verbose)
        return test_result

    def train_on_batch(self,
                       i_w, i_r, i_f, i_a,
                       t_w, t_r, t_f, t_a,
                       t_w_c, t_r_c):
        train_result = self.model.train_on_batch(
            [
                i_w, i_r, i_f, i_a,
                t_w, t_r, t_f, t_a,
            ], [
                t_w_c, t_r_c
            ])
        return train_result

    def test_on_batch(self,
                      i_w, i_r, i_f, i_a,
                      t_w, t_r, t_f, t_a,
                      t_w_c, t_r_c,
                      sample_weight=None):
        test_result = self.model.test_on_batch(
            [
                i_w, i_r, i_f, i_a,
                t_w, t_r, t_f, t_a,
            ], [
                t_w_c, t_r_c
            ],
            sample_weight)
        return test_result


    def predict2(self,
                i_w, i_r, i_f, i_a,
                t_w, t_r, t_f, t_a,
                batch_size=1, verbose=0):
        """ Return the output from softmax layer. """
        predict_result = self.model.predict(
            [
                i_w, i_r, i_f, i_a,
                t_w, t_r, #t_f, t_a,
            ],
            batch_size, verbose)
        return predict_result

    # for backward compatibility with validation tests:
    def predict(self,
                i_w, i_r, #i_f, i_a,
                t_w, t_r, #t_f, t_a,
                batch_size=1, verbose=0):
        return self.predict2(
            i_w, i_r,
            np.full( i_r.shape, self.missing_frame_id),
            np.full( i_r.shape, self.missing_anim_id),
            #self.dummy_frame_np, self.dummy_anim_np,
            t_w, t_r,
            np.full( t_r.shape, self.missing_frame_id),np.full( t_r.shape, self.missing_anim_id), # self.t_dummy, self.t_dummy,
            batch_size, verbose)
                    
    def predict_word2(self,
                     i_w, i_r, i_f, i_a,
                     t_w, t_r, t_f, t_a,
                     batch_size=1, verbose=0):
        """ Return predicted target word from prediction. """
        predict_result = self.predict2(
            i_w, i_r, i_f, i_a,
            t_w, t_r, t_f, t_a,
            batch_size, verbose)
        return np.argmax(predict_result[0], axis=1)

    # for backward compatibility with validation tests:
    def predict_word(self,
                     i_w, i_r, #i_f, i_a,
                     t_w, t_r, #t_f, t_a,
                     batch_size=1, verbose=0):
        return self.predict_word2(
            i_w, i_r, self.dummy_frame_np, self.dummy_anim_np,
            t_w, t_r,
            np.full( t_r.shape, self.missing_frame_id),np.full( t_r.shape, self.missing_anim_id), # self.t_dummy, self.t_dummy,
            batch_size, verbose)
                    
    def predict_role2(self,
                     i_w, i_r, i_f, i_a,
                     t_w, t_r, t_f, t_a,
                     batch_size=1, verbose=0):
        """ Return predicted target role from prediction. """
        predict_result = self.predict2(
            i_w, i_r, i_f, i_a,
            t_w, t_r, t_f, t_a,
            batch_size, verbose)
        return np.argmax(predict_result[1], axis=1)

    # for backward compatibility with validation tests:
    def predict_role(self,
                     i_w, i_r, #i_f, i_a,
                     t_w, t_r, #t_f, t_a,
                     batch_size=1, verbose=0):
        return self.predict_role2(
            i_w, i_r,
            np.full( i_r.shape, self.missing_frame_id),
            np.full( i_r.shape, self.missing_anim_id), #self.t_dummy, self.t_dummy,
#            self.dummy_frame_np, self.dummy_anim_np,
            t_w, t_r,
            np.full( t_r.shape, self.missing_frame_id),
            np.full( t_r.shape, self.missing_anim_id), #self.t_dummy, self.t_dummy,
            batch_size, verbose)

        
    def p_words2(self,
                i_w, i_r, i_f, i_a,
                t_w, #dummy, #t_w,
                t_r,
                t_f=None, t_a = None,
                batch_size=1, verbose=0):
        """ Return the output scores given target words. """
        predict_result = self.predict2(
            i_w, i_r, i_f, i_a,
            t_w, #dummy, #self.missing_word_id,
            t_r, t_f, t_a,
            batch_size, verbose)
        return predict_result[0][list(range(batch_size)), list(t_w)]
    # for backward compatibility with validation tests:
    def p_words(self,
                i_w, i_r, #i_f, i_a,
                t_w, t_r, #t_f, t_a,
                batch_size=1, verbose=0):
        return self.p_words2(
            i_w, i_r,
            #self.dummy_frame_np, self.dummy_anim_np,
            np.full( i_r.shape, self.missing_frame_id),np.full( i_r.shape, self.missing_anim_id),
            t_w, #np.full( t_r.shape, self.missing_word_id), #self.t_dummy, #t_w,
            t_r,
            np.full( t_r.shape, self.missing_frame_id),np.full( t_r.shape, self.missing_anim_id), #self.t_dummy, self.t_dummy,
            batch_size, verbose)
                        
    def p_roles2(self,
                i_w, i_r, i_f, i_a,
                t_w, t_r,
                t_f, t_a,
                batch_size=1, verbose=0):
        """ Return the output scores given target roles. """
        predict_result = self.predict2(
            i_w, i_r, i_f, i_a,
            t_w, t_r, #dummy, #self.missing_role_id,
            t_f, t_a,
            batch_size, verbose)
        return predict_result[1][list(range(batch_size)), list(t_r)]
    # for backward compatibility with validation tests:
    def p_roles(self,
               i_w, i_r, #i_f, i_a,
               t_w, t_r, #t_f, t_a,
               batch_size=1, verbose=0):
        return self.p_roles2(
            i_w, i_r, self.dummy_frame_np, self.dummy_anim_np,
            t_w, t_r,
            np.full( t_r.shape, self.missing_frame_id),np.full( t_r.shape, self.missing_anim_id), #self.t_dummy, self.t_dummy,
            batch_size, verbose)
                        
    def top_words2(self,
                  i_w, i_r, i_f, i_a,
                  t_w,
                  t_r, t_f=None, t_a = None,
                  topN=20, batch_size=1, verbose=0):
        """ Return top N target words given context. """
        predict_result = self.predict2(
            i_w, i_r, i_f, i_a,
            t_w, #dummy, #self.dummy_word_np,
            t_r, t_f, t_a,
            batch_size, verbose)[0]
        rank_list = np.argsort(predict_result, axis=1)[0]
        return rank_list[-topN:][::-1]
        # return [r[-topN:][::-1] for r in rank_list]

    # for backward compatibility with validation tests:
    def top_words(self,
                  i_w, i_r, #i_f, i_a,
                  t_w, t_r, #t_f, t_a,
                  topN=20, batch_size=1, verbose=0):
        return self.top_words2(
            i_w, i_r, self.dummy_frame_np, self.dummy_anim_np,
            t_w, t_r,
            np.full( t_r.shape, self.missing_frame_id),np.full( t_r.shape, self.missing_anim_id), #self.t_dummy, self.t_dummy,
            topN, batch_size, verbose)
                                
    # TODO
    def list_top_words2(self,
                       i_w, i_r, i_f, i_a,
                       dummy,
                       t_r,
                       t_f=None, t_a = None,     
                       topN=20, batch_size=1, verbose=0):
        """ Return a list of decoded top N target words.
            (Only for reference, can be removed.)
        """
        top_words_lists = self.top_words2(
            i_w, i_r, i_f, i_a,
            dummy,
            t_r, t_f, t_a, 
            topN, batch_size, verbose)
        print(type(top_words_lists))
        result = []
        for i in range(batch_size):
            top_words_list = top_words_lists[i]
            result.append([self.word_decoder[w] for w in top_words_list])
        return result
    # for backward compatibility with validation tests:
    def list_top_words(self,
                       i_w, i_r, #i_f, i_a,
                       t_w, t_r, #t_f, t_a,
                       topN=20, batch_size=1, verbose=0):
        return self.list_top_words2(
            i_w, i_r, self.dummy_frame_np, self.dummy_anim_np,
            t_w, t_r,
            np.full( t_r.shape, self.missing_frame_id),np.full( t_r.shape, self.missing_anim_id), #self.t_dummy, self.t_dummy,
            topN, batch_size, verbose)

                

    def summary(self):
        self.model.summary()


