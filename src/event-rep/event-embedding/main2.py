''' This module contains example runner of non-incremental model of role-filler. 

    Author: Tony Hong

    Ref: Ottokar Tilk, Event participant modelling with neural networks, EMNLP 2016
'''

import os, sys, time, re
import pickle as cPickle


import numpy as np
from tensorflow.keras.optimizers import Adagrad
from tensorflow.keras.callbacks import Callback, ModelCheckpoint, EarlyStopping, LambdaCallback, TerminateOnNaN, ReduceLROnPlateau
import tensorflow.keras.backend as K

# Configuration of environment
# SRC_DIR = os.path.dirname(os.path.abspath(__file__))
# sys.path.append(os.path.join(SRC_DIR, 'evaluation/'))
# sys.path.append(os.path.join(SRC_DIR, 'model/'))

import config, utils, model_builder
#from batcher import generator
import batcher
import batcher_fran

from model import *
from evaluation import *
import argparse

from roles import *

#DATA_PATH = config.DATA_VERSION
#MODEL_PATH = config.MODEL_VERSION




def run(experiment_name, data_version, model_name, load_previous,
        learning_rate, learning_rate_decay, 
        batch_size, batch_size_decay, min_batch_size,
        samples_per_epoch, epochs,
        workers, #=2
        print_after_batches, save_after_steps,
        L1_reg, L2_reg,
#        n_factors_emb,
        n_hidden,
        n_factors_emb_word,n_factors_emb_role,n_factors_emb_frame,n_factors_emb_anim,
        using_dropout, dropout_rate, loss_weights):

    min_lr=0.001
    
    print('Meta parameters: ')
    print('experiment_name: ', experiment_name)
    print('data_version: ',    data_version)
    print('model_name: ',      model_name)
    print('learning_rate: ',       learning_rate)
    print('learning_rate_decay: ', learning_rate_decay)
    print('batch_size: ', batch_size)
    print('min_batch_size: ', min_batch_size)
    print('batch_size_decay: ', batch_size_decay)
    print('samples_per_epoch: ', samples_per_epoch)
    print('epochs: ', epochs)
    print('n_factors_emb_word (should be sum of role + frame + anim sizes): ', n_factors_emb_word)
    print('n_factors_emb_frame: ', n_factors_emb_frame)
    print('n_factors_emb_anim: ', n_factors_emb_anim)
    print('n_factors_emb_role: ', n_factors_emb_role)
#    print('n_factors_emb_role (should be sum of the above): ', n_factors_emb_role)
    
    print('n_hidden: ', n_hidden)
    print('using_dropout: ', using_dropout)
    print('dropout_rate: ', dropout_rate)
    print('loss_weights: ', loss_weights)
    print('')

    start_time = time.perf_counter()

    experiment_name_prefix = "%s_" % experiment_name
    tmp_exp_name = experiment_name_prefix + "temp"
    final_exp_name = experiment_name_prefix + "final"
#    e27_exp_name = experiment_name_prefix + "e27"

#    with open(DATA_PATH + "description", 'rb') as data_file:
    with open(os.path.join(DATA_PATH, "description"), 'rb') as data_file:
        description = cPickle.load(data_file)
        print (str(os.path.join(DATA_PATH, "description"))) # DATA_PATH + "description"
        print (description.keys())
        word_vocabulary = description['word_vocabulary']
        role_vocabulary = description['role_vocabulary']
        unk_word_id = description['unk_word_id']   #['NN_unk_word_id']
        unk_role_id = description['unk_role_id']

        if 'frame_vocabulary' in description:
            frame_vocabulary= description['frame_vocabulary']
            anim_vocabulary = description['anim_vocabulary']
            unk_frame_id= description['unk_frame_id']
            unk_anim_id = description['unk_anim_id']
        else:
            frame_vocabulary= {}
            anim_vocabulary = {}
            unk_frame_id= -2
            unk_anim_id = -2
        
        if 'missing_word_id' in description:
            missing_word_id = description['missing_word_id']    # [NN_missing_word_id']
        else:
            missing_word_id = unk_word_id + 1  
            print ("Adding missing word ID", missing_word_id) # uncomment the +1s and fix in data converter too!
            
        if 'missing_frame_id' in description:
            missing_frame_id= description['missing_frame_id']   # ['NN_missing_frame_id']
        else:
            missing_frame_id = unk_frame_id + 1
            print ("Adding missing frame ID", missing_frame_id)  # uncomment the +1s and fix in data converter too!
            
        if 'missing_anim_id' in description:
            missing_anim_id = description['missing_anim_id']    # ['NN_missing_anim_id']
        else:
            missing_anim_id = unk_anim_id + 1
            print ("Adding missing anim ID", missing_anim_id)  # uncomment the +1s and fix in data converter too!

        if 'missing_role_id' in description:
            missing_role_id = description['missing_role_id']
        else:
            missing_role_id = unk_role_id + 1
            print ("Adding missing role ID", missing_role_id)  # uncomment the +1s and fix in data converter too!
    
        print ("(unk_word_id, unk_role_id, missing_word_id)", (unk_word_id, unk_role_id, missing_word_id))
    
    print ('... building the model')

    rng = np.random

    if missing_word_id != unk_word_id:
        word_vocabulary['<NULL>'] = missing_word_id
#        role_vocabulary['<NULL>'] = missing_role_id
        frame_vocabulary['<NULL>']= missing_frame_id
        anim_vocabulary['<NULL>'] = missing_anim_id
    
    word_vocabulary['<UNKNOWN>'] = unk_word_id
    role_vocabulary[Roles.TEST_ROLE_OTHER] = unk_role_id
    frame_vocabulary['<UNKNOWN>']= unk_frame_id
    anim_vocabulary['<UNKNOWN>'] = unk_anim_id  # not needed but added for consistency
    
    n_word_vocab = len(word_vocabulary)
    n_role_vocab = len(role_vocabulary)

    has_frames_or_anim = (len(frame_vocabulary) >= 3 and n_factors_emb_frame > 1) or (n_factors_emb_anim > 1)
    
    adagrad = Adagrad(lr=learning_rate, epsilon=1e-08, decay=0.0)
#    adagrad = Adagrad(lr=learning_rate, epsilon=1e-08, decay=learning_rate_decay)

    if re.search('NNRF', model_name):
        model = NNRF(n_word_vocab, n_role_vocab, 
            n_factors_emb_word, 512, n_hidden, word_vocabulary, role_vocabulary, unk_word_id, unk_role_id, missing_word_id, 
            using_dropout, dropout_rate, optimizer=adagrad, loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    else:
        if not has_frames_or_anim:  #len(frame_vocabulary) < 3:          # no Frames or Animacy
            model = eval(model_name)(
                len(word_vocabulary), len(role_vocabulary), #n_word_vocab, n_role_vocab,
                n_factors_emb_word,
                n_hidden,
                word_vocabulary, role_vocabulary,
                unk_word_id, unk_role_id,
                missing_word_id,
                using_dropout, dropout_rate, optimizer=adagrad, loss='sparse_categorical_crossentropy', metrics=['accuracy'], loss_weights=loss_weights)
        else:                                  # with Frames and Anim:
            model = eval(model_name)( 
                n_hidden,
                n_factors_emb_word,n_factors_emb_role,n_factors_emb_frame,n_factors_emb_anim,
                word_vocabulary, role_vocabulary, frame_vocabulary, anim_vocabulary,
                unk_word_id,     unk_role_id,     unk_frame_id,     unk_anim_id,
                missing_word_id, missing_role_id, missing_frame_id,missing_anim_id,
                using_dropout, dropout_rate, optimizer=adagrad, loss='sparse_categorical_crossentropy', metrics=['accuracy'], loss_weights=loss_weights)

    # else:
    #     sys.exit('No such model!!!')
        
    print ("clean model summary:")
    model.summary()

    print (model.model.metrics_names)

    epoch = 0
    best_epoch = -1 # 0
    best_validation_cost = np.inf
    global_train_epoch = []
    global_train_history = {}

    if load_previous:
       print ("Attempting to restart a stopped training session...")
       model_descr = model_builder.load_description(MODEL_PATH, experiment_name) #,  model_name))
       if not has_frames_or_anim: 
          learning_rate, global_train_history, best_validation_cost, \
          best_epoch, epoch = \
              model.load(MODEL_PATH, experiment_name, model_descr) #model_name,)
       else:
          learning_rate, learning_rate_decay, global_train_history, best_validation_cost, \
          best_epoch, epoch = \
              model.load(MODEL_PATH, experiment_name, model_descr) #model_name,)
       for e in range(epoch):
           global_train_epoch.append("old_epoch_%s" % (e+1))
       print ("Recovered experiment until epoch %s." % epoch)

    max_output_length = 0
    
#    valid_sample_size = config.VALID_SIZE
#    test_sample_size  = config.TEST_SIZE
    valid_sample_size = config.getValidationSetSize(data_version)
    test_sample_size  = config.getTestSetSize(data_version)
    
    train_steps = samples_per_epoch / batch_size
    valid_steps = valid_sample_size / batch_size
    test_steps = test_sample_size / batch_size
    # # DEBUG
    # valid_steps = 10
    # test_steps = 10

    save_after_steps = save_after_steps + 1

    training_verbose = 2
    max_q_size = 10
    #workers = 2
    pickle_safe = True


    def thematic_fit_evaluation(model_name, experiment_name, model, print_result):
        result = dict()
        # Pado, Mcrae A0/A1/A2
        tempdict = dict()
        tempdict['pado'], _, _ = eval_pado_mcrae(model_name, experiment_name, 'pado', model, print_result)
        tempdict['mcrae'], _, _ = eval_pado_mcrae(model_name, experiment_name, 'mcrae', model, print_result)
#        tempdict['pado_fixed'] = eval_pado_mcrae(model_name, experiment_name, 'pado_fixed', model=model, print_result=print_result)
#        tempdict['mcrae_fixed'] = eval_pado_mcrae(model_name, experiment_name, 'mcrae_fixed', model=model, print_result=print_result)
        for k, v in tempdict.items():
            try:
                for sk, sv in v.items():
                    result[k + '-' + sk] = sv
            except: # v is not a dict:
                print("WARNING: expected dict in %s: %s ..." % (k,str(v)[:40]))
#                result[k + '-' + ' misc.'] = v
              
        r, _, _, _, _ = eval_MNR_LOC(model_name, experiment_name, 'AM-MNR', model, print_result, skip_header=True)
        result['mcrae-MNR'] = round(r, 4)
        r2, _, _, _, _ = eval_MNR_LOC(model_name, experiment_name, 'AM-LOC', model, print_result)
        result['mcrae-LOC'] = round(r2, 4)

        rho_obj, _, _, rho_fil, _, _, rho_gre, _, _ = eval_greenberg_all(model_name, experiment_name, model, print_result)
        result['GObject'] = round(rho_obj, 4)
        result['GFiller'] = round(rho_fil, 4)
        result['greenberg'] = round(rho_gre, 4)

# need to fix bug here:
        correct, _, acc = eval_bicknell_switch(model_name, experiment_name, 'bicknell', model, print_result, switch_test=False)
        result['bicknell'] = (acc, correct)

        correlation = eval_GS(model_name, experiment_name, 'GS2013data.txt', model, print_result)
        result['GS'] = round(correlation, 4)

        return result


    class CallbackContainer(Callback):
        """Callback that records events into a `History` object.
        """
        def on_train_begin(self, logs=None):
            self.epoch = global_train_epoch     #[]
            self.history = global_train_history #{}
            self.best_validation_cost = best_validation_cost #-1
            self.best_epoch = best_epoch        #-1

        def on_epoch_begin(self, epoch, logs):
            self.epoch_start = time.perf_counter()
            print ("Starting epoch %s  %s" % (epoch, time.ctime()))

        def on_batch_end(self, batch, logs):
            batch_n = batch + 1
            epoch_n = len(self.epoch)
            if batch_n % print_after_batches == 0:
                elapsed_time = time.perf_counter() - self.epoch_start
                output = "batch %d; %d samples; %.1f sps; " % (
                    batch_n, 
                    batch_n * batch_size, 
                    batch_n * batch_size / (elapsed_time + 1e-32))
                print (output)
            if batch_n % save_after_steps == 0:
                try:
                    model.save(MODEL_PATH, tmp_exp_name, model_name, learning_rate, learning_rate_decay, self.history, self.best_validation_cost, self.best_epoch, epoch_n)
                except TypeError: # v1 model (without Frames / Anim or learning_rate_decay param)
                    model.save(MODEL_PATH, tmp_exp_name, model_name, learning_rate,   self.history, self.best_validation_cost, self.best_epoch, epoch_n)
                print ("Temp model saved! ")

        def on_epoch_end(self, epoch, logs=None):
            epoch_n = epoch + 1
            logs = logs or {}
            self.epoch.append(epoch_n)
            
            print("Current model optimizer LR: %.3f" % float(K.eval(model.optimizer.lr)))
            print ('Validating %s %s %s iter %d ... %s' % (experiment_name, data_version, model_name, epoch_n, time.ctime() ))
            valid_result = model.model.evaluate(
                    x = batcher.generator(os.path.join(DATA_PATH, "NN_dev"), model_name,
                                          unk_word_id,     unk_role_id, 
                                          missing_word_id,  
                                          role_vocabulary,
                                          random=False, batch_size=batch_size) \
                        if (not has_frames_or_anim) else \
                        #(len(frame_vocabulary) < 3) else \
                                batcher_fran.generator(os.path.join(DATA_PATH, "NN_dev"), model_name,
                                          unk_word_id,     unk_role_id, unk_frame_id,     unk_anim_id,
                                          missing_word_id,              missing_frame_id, missing_anim_id,
                                          role_vocabulary,
                                          random=False, batch_size=batch_size) ,
                    steps = valid_sample_size / batch_size, # test_steps, 
                    max_queue_size = 1, 
                    workers = 1, 
                    use_multiprocessing = False
                )
            print ('validation_set_result', valid_result)

            for i, m in enumerate(model.model.metrics_names):
                logs['valid_' + m] = valid_result[i]

            # print model.model.get_layer("softmax_word_output").get_weights()[1]

            result = thematic_fit_evaluation(model_name, experiment_name, model, print_result=False)
            for k, v in result.items():
                logs[k] = v

            # print model.model.get_layer("softmax_word_output").get_weights()[1]

            for k, v in logs.items():
                self.history.setdefault(k, []).append(v)

            if epoch_n > 1 and self.history['valid_loss'][-1] < self.history['valid_loss'][-2]:
                print ("Best model saved! ")
                self.best_validation_cost = np.min(np.array(self.history['valid_loss']))
                self.best_epoch = np.argmin(np.array(self.history['valid_loss'])) + 1
                try:
                    model.save(MODEL_PATH, final_exp_name, model_name, learning_rate, learning_rate_decay,
                           self.history, self.best_validation_cost, self.best_epoch, epoch_n)
                except TypeError: # v1 model (without Frames / Anim or learning_rate_decay param)
                    model.save(MODEL_PATH, final_exp_name, model_name, learning_rate,
                           self.history, self.best_validation_cost, self.best_epoch, epoch_n)
                print ('best_validation_cost, best_epoch, epoch_n', self.best_validation_cost, self.best_epoch, epoch_n)
            else:
                print("loss on validation set didn't improve -- not saving this model.")
                
            for k, v in sorted(self.history.items()):
                    print (k, v)

            print ("Saving current model... %s-%s-%s " % (experiment_name, data_version, model_name,))
            try:
                model.save(MODEL_PATH, experiment_name, model_name, learning_rate, learning_rate_decay,
                       self.history, self.best_validation_cost, self.best_epoch, epoch_n)
            except TypeError: # v1 model (without Frames / Anim or learning_rate_decay param)
                model.save(MODEL_PATH, experiment_name, model_name, learning_rate, 
                       self.history, self.best_validation_cost, self.best_epoch, epoch_n)
            print ("Current model saved! ")


    callback_container = CallbackContainer()
    callback_container.epoch   = global_train_epoch   #[]
    callback_container.history = global_train_history #{}

    # saves the backup model weights after each epoch if the validation loss decreased
    # backup_checkpointer = ModelCheckpoint(filepath='backup_' + experiment_name + '.hdf5', verbose=1, save_best_only=True)

    stopper = EarlyStopping(monitor='valid_loss', min_delta=1e-3, patience=5, verbose=1)
    naNChecker = TerminateOnNaN()
    reduce_lr = ReduceLROnPlateau(monitor='valid_loss', factor=0.1,
              patience=3, min_lr=min_lr) # min_lr=0.001

    print ('Training...', time.ctime())
    train_start = time.perf_counter()
    while True:
        print("\nTraining batch size is now %s samples" % batch_size)
        model.optimizer = Adagrad(lr=learning_rate, epsilon=1e-08, decay=0) # decay=learning_rate_decay)
#        model.optimizer = Adadelta(lr=learning_rate, epsilon=1e-08, rho=0.95)        
        print("new model optimizer: %s" % model.optimizer.__class__.__name__)
        print("new model optimizer LR: %.3f" % float(K.eval(model.optimizer.lr)))   
        model.model.fit(
            x = batcher.generator(os.path.join(DATA_PATH, "NN_train"), model_name,
                                          unk_word_id,     unk_role_id, 
                                          missing_word_id,  
                                          role_vocabulary,
                                          random=False, rng=rng, batch_size=batch_size) \
#            if (len(frame_vocabulary) < 3) else \
            if (not has_frames_or_anim) else \
            batcher_fran.generator(os.path.join(DATA_PATH, "NN_train"), model_name,
                                   unk_word_id, unk_role_id, unk_frame_id,     unk_anim_id,
                                   missing_word_id,          missing_frame_id, missing_anim_id,
                                   role_vocabulary,
                                   random=True, rng=rng, batch_size=batch_size),
            steps_per_epoch = samples_per_epoch / batch_size, # train_steps,
            initial_epoch   = len(callback_container.epoch),
            epochs = epochs + len(callback_container.epoch), 
            verbose = training_verbose,
            workers = workers,
            max_queue_size = max_q_size,
            use_multiprocessing = pickle_safe,
            callbacks = [callback_container, stopper, naNChecker, reduce_lr]
        )
        print (callback_container.epoch)
        for k, v in sorted(callback_container.history.items()):
            print (k, v)

        global_train_epoch = callback_container.epoch
        global_train_history = callback_container.history
    
        train_end = time.perf_counter()
        print ('train and validate time: %f, sps: %f for batch size %d' \
            % (train_end - train_start,
               float(samples_per_epoch) / (train_end - train_start), #train_steps * batch_size / (train_end - train_start),
               batch_size))

        if batch_size_decay >= 1.0:
            print('No decay specified, training is done')
            break
        else:
            batch_size = (int) (batch_size_decay * batch_size)
            learning_rate = learning_rate * batch_size_decay
            if batch_size < min_batch_size: 
                print("Reached minimum batch size, training is done. Last batch size: %d" % (float(batch_size_decay) / batch_size))
                break
            

    print ('Testing...',  time.ctime())
    test_start = time.perf_counter()

    description_best = model_builder.load_description(MODEL_PATH, experiment_name)
    model.load(MODEL_PATH, experiment_name, description_best)

    test_result = model.model.evaluate(
            x = batcher.generator(os.path.join(DATA_PATH, "NN_test"), model_name,
                                          unk_word_id,     unk_role_id, 
                                          missing_word_id,  
                                          role_vocabulary,
                                          random=False, batch_size=batch_size) \
#                        if (len(frame_vocabulary) < 3) else \
                        if (not has_frames_or_anim) else \
                        batcher_fran.generator(os.path.join(DATA_PATH, "NN_test"), model_name,
                                  unk_word_id, unk_role_id, unk_frame_id,     unk_anim_id,
                                  missing_word_id,        missing_frame_id, missing_anim_id,
                                  role_vocabulary,
                                  random=False, batch_size=batch_size),
            steps = test_sample_size / batch_size, #test_steps, 
            max_queue_size = 1, 
            workers = 1, 
            use_multiprocessing = False
        )
    print ('test_result', test_result)
    print ('for metrics' , model.model.metrics_names)

    test_end = time.perf_counter()
    print ('test time: %f, sps: %f' % (test_end - test_start, test_sample_size / (test_end - test_start)))
                                      #test_steps * batch_size / (test_end - test_start))

 #   result = thematic_fit_evaluation(model_name, experiment_name, model, False)
 #   for k, v in sorted(result.items()):
 #       print "Test", k, v
                
    end_time = time.perf_counter()
    print ("Total running time %.2fh" % ((end_time - start_time) / 3600.))
    print  (time.ctime())

    print ('Optimization for %s %s %s complete. Best validation cost of %f obtained at epoch %i' % (experiment_name, data_version, model_name, callback_container.best_validation_cost, callback_container.best_epoch))



if __name__ == '__main__':
    '''Check model/__init__.py for the classname of each model
    '''

    parser = argparse.ArgumentParser(description='train semantic fit model')
    parser.add_argument("model_name",   type=str,
                        help="model_name")
    parser.add_argument("data_version", type=str,
                        help="data_version corresponding to format_dataset*.py output folder")
    parser.add_argument("experiment_version", type=str,
                        help="experiment_version, e.g., current date")
    parser.add_argument("--load_previous",    type=bool, default=False,
                        help="load previously trained model? NEED TO REIMPLEMENT")
    parser.add_argument("--learning_rate",    type=float,default=config.LEARNING_RATE,
                        help="learning_rate")
    parser.add_argument("--learning_rate-decay",type=float,default=config.LEARNING_RATE_DECAY,
                        help="learning_rate")
    parser.add_argument("--batch_size",       type=int,  default=config.BATCH_SIZE,
                        help="batch size")
    parser.add_argument("--min_batch_size",       type=int,  default=512, #config.MIN_BATCH_SIZE,
                        help="min batch size if decreasing")
    parser.add_argument("--batch_size_decay",       type=float,  default=1.0, #config.BATCH_SIZE_DECAY,
                        help="batch size decay: by how much to decrease it (0..1) 1=no decrease")
    parser.add_argument("--samples_per_epoch",type=str,  default="1.0", #config.getSampleEpochs(data_version),
                        help="number of samples per epoch (int). If float, interpreted as fraction of the training set. Default: 1.0 (entire training set). Use for debugging if you want to use a smaller training set.")
    parser.add_argument("--epochs",           type=int,  default=config.EPOCHS,
                        help="number of iterations")
    parser.add_argument("--workers",           type=int,  default=2,
                        help="number of workers (cores, threads) available for training")
    parser.add_argument("--loss_weight_role",type=float, default=config.LOSS_WEIGHT_ROLE,
                        help="loss_weight_role")
    parser.add_argument("--print_after_batches",type=int,default=config.PRINT_AFTER,
                        help="print stats after every nn batches")
    parser.add_argument("--save_after_steps",type=int,   default=config.SAVE_AFTER,
                        help="same temp model after every nn batches")
    parser.add_argument("--role_set",type=str,   default=config.ROLES_CLS.__name__,
                        help="Role set for training and evaluation (see roles.py)")
    parser.add_argument("--use_animacy",type=bool,   default=False,
                        help="Use animacy in model features (relevant if dataset contains animacy info)")   
    parser.add_argument("--use_framenet",type=bool,   default=False,
                        help="Use FrameNet semantic frames in model features (relevant if dataset contains FrameNet frame info)")   
    args = parser.parse_args()

    use_frames_anim = args.use_framenet or args.use_animacy
    
    n_factors_emb_word = config.FACTOR_NUM
    n_factors_emb_frame= 32 if args.use_framenet else (1 if use_frames_anim else 0) #32
    n_factors_emb_anim =  8 if args.use_animacy  else (1 if use_frames_anim else 0) # 4
#    n_factors_emb_role = n_factors_emb_word - n_factors_emb_frame - n_factors_emb_anim
    n_factors_emb_role = n_factors_emb_word + n_factors_emb_frame + n_factors_emb_anim
    n_hidden = config.HIDDEN_NUM
    use_dropout = config.USE_DROPOUT
    dropout_rate = config.DROPOUT_RATE

    experiment_name = args.model_name + '_' + args.data_version + '_' + args.experiment_version

    DATA_PATH  = config.getDataVersion(args.data_version)
    MODEL_PATH = config.MODEL_PATH # config.getModelVersion(model_name) # experiment output dir

    try:
        samples_per_epoch = int(args.samples_per_epoch)
    except:
#        samples_per_epoch = config.getSampleEpochs(args.data_version) * float(args.samples_per_epoch)
        samples_per_epoch = int(float(args.samples_per_epoch) * config.getTrainingSetSize(args.data_version))
    print("samples_per_epoch = %s" % samples_per_epoch)

    config.ROLES_CLS = eval(args.role_set)
    print ("Role set: %s\nTraining roles: %s" % (args.role_set, config.ROLES_CLS.TRAIN_ROLES))

    
    run(experiment_name, args.data_version, args.model_name, args.load_previous,
        args.learning_rate, args.learning_rate_decay,
        args.batch_size, args.batch_size_decay, args.min_batch_size,
        samples_per_epoch, args.epochs,
        args.workers,
        args.print_after_batches, args.save_after_steps,
        L1_reg=0.00, L2_reg=0.00,
        n_hidden=n_hidden,
#        n_factors_emb=n_factors_emb,
        n_factors_emb_word=n_factors_emb_word, n_factors_emb_role=n_factors_emb_role, n_factors_emb_frame=n_factors_emb_frame, n_factors_emb_anim=n_factors_emb_anim, 
        using_dropout=use_dropout, dropout_rate=dropout_rate, loss_weights=[1., args.loss_weight_role])

                                                                                                                           
