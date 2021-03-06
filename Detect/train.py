"""
Detect 训练
author: 王建坤
date: 2018-9-10
"""
import os
import numpy as np
import tensorflow as tf
from Detect import utils
from nets import alexnet, vgg, resnet_v2, inception_v4, inception_resnet_v2
import tensorflow.contrib.slim as slim
from sklearn.model_selection import train_test_split
import time


MAX_STEP = 1200
LEARNING_RATE_BASE = 0.001
LEARNING_RATE_DECAY = 0.96
# 训练信息和保存权重的gap
INFO_STEP = 20
SAVE_STEP = 200
# 类别数和图片尺寸
CLASSES = 8
IMG_SIZE = 299
BATCH_SIZE = 128
GLOBAL_POOL = True


def train(model='Alex', inherit=False, fine_tune=False):
    """
    train a specified model
    :param model: the train model name
    :param inherit: whether to continue training
    :param fine_tune: whether to fine tuning
    :return: none
    """
    # 占位符
    x = tf.placeholder(tf.float32, [None, IMG_SIZE, IMG_SIZE, 3], name="x_input")
    y_ = tf.placeholder(tf.uint8, [None], name="y_input")
    my_global_step = tf.Variable(0, name='global_step', trainable=False, dtype=tf.int64)

    # 加载数据集
    images = np.load('../data/data_'+str(IMG_SIZE)+'.npy')
    labels = np.load('../data/label_'+str(IMG_SIZE)+'.npy')
    train_data, val_data, train_label, val_label = train_test_split(images, labels, test_size=0.2, random_state=222)

    # 模型保存路径，模型名，预训练文件路径，前向传播
    if model == 'Alex':
        log_path = "../log/Alex"
        model_name = 'alex.ckpt'
        if fine_tune:
            print('Error: alex has no pre-train model')
            return
        y, _ = alexnet.alexnet_v2(x,
                                  num_classes=CLASSES,      # 分类的类别
                                  is_training=True,         # 是否在训练
                                  dropout_keep_prob=1.0,    # 保留比率
                                  spatial_squeeze=True,     # 压缩掉1维的维度
                                  global_pool=GLOBAL_POOL)  # 输入不是规定的尺寸时，需要global_pool
    elif model == 'VGG':
        log_path = "../log/VGG"
        model_name = 'vgg_299.ckpt'
        fine_tune_path = '../data/vgg_16_2016_08_28/vgg_16.ckpt'
        y, _ = vgg.vgg_16(x,
                          num_classes=CLASSES,
                          is_training=True,
                          dropout_keep_prob=0.8,
                          spatial_squeeze=True,
                          global_pool=GLOBAL_POOL)
        variables_to_restore = slim.get_variables_to_restore(exclude=['vgg_16/fc8'])

    elif model == 'Incep':
        log_path = "E:/alum/log/Incep"
        model_name = 'incep.ckpt'
        fine_tune_path = 'E:/alum/weight/inception_v4_2016_09_09/inception_v4.ckpt'
        y, _ = inception_v4.inception_v4(x,
                                         num_classes=CLASSES,
                                         is_training=True,
                                         dropout_keep_prob=0.8,
                                         reuse=None,
                                         scope='InceptionV4',
                                         create_aux_logits=True)
        variables_to_restore = slim.get_variables_to_restore(exclude=['InceptionV4/Logits', 'InceptionV4/AuxLogits'])

    elif model == 'Res':
        log_path = "E:/alum/log/Res"
        model_name = 'res.ckpt'
        fine_tune_path = 'E:/alum/weight/resnet_v2_50_2017_04_14/resnet_v2_50.ckpt'
        y, _ = resnet_v2.resnet_v2_50(x,
                                      num_classes=CLASSES,
                                      is_training=True,
                                      global_pool=GLOBAL_POOL,
                                      output_stride=None,
                                      spatial_squeeze=True,
                                      reuse=None,
                                      scope='resnet_v2_50')
        variables_to_restore = slim.get_variables_to_restore(exclude=['resnet_v2_50/logits'])

    elif model == 'IncepRes':
        log_path = "E:/alum/log/IncepRes"
        model_name = 'incepres.ckpt'
        fine_tune_path = 'E:/alum/weight/inception_resnet_v2_2016_08_30/inception_resnet_v2_2016_08_30.ckpt'
        y, _ = inception_resnet_v2.inception_resnet_v2(x,
                                                       num_classes=CLASSES,
                                                       is_training=True,
                                                       dropout_keep_prob=1.0,
                                                       reuse=None,
                                                       scope='InceptionResnetV2',
                                                       create_aux_logits=True,
                                                       activation_fn=tf.nn.relu)
        variables_to_restore = slim.get_variables_to_restore(exclude=['InceptionResnetV2/Logits',
                                                                      'InceptionResnetV2/AuxLogits'])
    else:
        print('Error: model name not exist')
        return

    y_hot = tf.one_hot(y_, CLASSES)
    cross_entropy = tf.nn.softmax_cross_entropy_with_logits(logits=y, labels=y_hot, name='entropy')
    loss = tf.reduce_mean(cross_entropy, name='loss')
    learning_rate = tf.train.exponential_decay(LEARNING_RATE_BASE, my_global_step, 100, LEARNING_RATE_DECAY)
    optimizer = tf.train.AdamOptimizer(learning_rate)
    train_op = optimizer.minimize(loss, global_step=my_global_step)
    correct = tf.equal(tf.argmax(y, 1), tf.argmax(y_hot, 1))
    accuracy = tf.reduce_mean(tf.cast(correct, "float"))

    # 模型保存的Saver
    saver = tf.train.Saver(tf.global_variables())
    init = tf.global_variables_initializer()

    # 训练迭代
    with tf.Session() as sess:
        step = 0
        # 是否使用预训练模型
        if fine_tune:
            print('finetune:', model)
            # 预训练模型的Saver
            init_fine_tune = slim.assign_from_checkpoint_fn(fine_tune_path, variables_to_restore,
                                                            ignore_missing_vars=True)
            sess.run(init)
            init_fine_tune(sess)
        # 是否继续训练，ckpt 有 model_checkpoint_path 和 all_model_checkpoint_paths 两个属性
        elif inherit:
            ckpt = tf.train.get_checkpoint_state(log_path)
            if ckpt and ckpt.model_checkpoint_path:
                global_step = ckpt.model_checkpoint_path.split('/')[-1].split('-')[-1]
                saver.restore(sess, ckpt.model_checkpoint_path)
                print(model, 'continue train from %s:' % global_step)
                step = int(global_step)
            else:
                print('Error: no checkpoint file found')
                return
        else:
            print(model, 'restart train:')
            sess.run(init)

        # 迭代
        while step < MAX_STEP:
            start_time = time.clock()
            image_batch, label_batch = utils.get_batch(train_data, train_label, BATCH_SIZE)
            # 如果输入是灰色图，要增加一维
            # image_batch = np.expand_dims(image_batch, axis=3)

            # 训练，损失值和准确率
            _, los, train_ac = sess.run([train_op, loss, accuracy], feed_dict={x: image_batch, y_: label_batch})
            end_time = time.clock()
            runtime = end_time - start_time

            step += 1
            # 训练信息和保存模型
            if step % INFO_STEP == 0 or step == MAX_STEP:
                val_ac = sess.run(accuracy, feed_dict={x: val_data, y_: val_label})
                print('step: %d, runtime: %.2f loss: %.4f, train accuracy: %.4f, test accuracy: %.4f' %
                      (step, runtime, los, train_ac, val_ac))

            if step % SAVE_STEP == 0:
                print('learning_rate: ', sess.run(learning_rate))
                checkpoint_path = os.path.join(log_path, model_name)
                saver.save(sess, checkpoint_path, global_step=step)


if __name__ == '__main__':
    train()
