import tensorflow as tf
import tensorflow.keras.backend as K

def custom_acc(y_true, y_pred):
    if y_pred.shape[1] == 7:  # role labels
        y_pred = tf.keras.backend.argmax(y_pred, axis=-1)
        return K.mean(K.equal(tf.cast(y_true, dtype=tf.int32), tf.cast(y_pred, dtype=tf.int32)))
    else: # word labels
        y_pred = tf.keras.backend.argmax(y_pred, axis=-1)
        return K.mean(K.equal(tf.cast(y_true, dtype=tf.int32), tf.cast(y_pred, dtype=tf.int32)))