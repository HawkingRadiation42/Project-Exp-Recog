import numpy as np
import src.adaboost as ab
import src.haar_features as haar
import src.utils as utils

# for processing time
import progressbar
from multiprocessing import cpu_count, Pool


def cascaded_classifier(pos_train_int_imgs, neg_train_int_imgs, pos_dev_int_imgs, neg_dev_int_imgs, max_cascade=3):
    # train a cascade of classifier which need to meet the overall detection rates & FPR
    # return: a list of strong classifiers (each one generated by AdaBoost algorithm)
    # rtype: list[list[haar.HaarLikeFeature]]

    # preset paramters
    d = .8 # TPR for each classifier (.9)
    f = .5 # FPR for each classifier
    F_target = .05 # target FPR for the cascaded classifier
    D_target = .80 # target TPR for the cascaded classifier (.90)

    D = np.ones(max_cascade, dtype=np.float64) # initialised TPR
    F = np.ones(max_cascade, dtype=np.float64) # initialised FPR
    n = np.zeros(max_cascade) # #classifiers in one cascade
    i = 0 # index of the number of cascade

    cascaded_classifiers = list()

    # parameters for AdaBoost algorithm
    min_feature_height = 4
    max_feature_height = 10
    min_feature_width = 4
    max_feature_width = 10

    # TRAINING DATA
    pos_train, neg_train = pos_train_int_imgs, neg_train_int_imgs

    '''
    Each stage in the cascade reduces the false positive rate and decreases the detection rate
    A target is selected for the minimum reduction in the false positives and the maximum decrease in detection
    Each stage is trained by adding features until the target detection and false positive rates are met 
    (determined on a validation set)
    Stages are added until the overall target for false positive and detection rate is met
    '''

    print("\ntraining the cascaded classifiers ...")
    # control the FPR for overall cascade lower than 0.05
    while F[i] > F_target or D[i] < D_target:

        # end when reaching maximum number of cascades
        if i == max_cascade:
            break

        i += 1 # cascade 0 does not count 
        F[i] = F[i - 1]
        D[i] = D[i - 1]

        print("\nadding features at cascade no %d with FPR controlled ..." % i)
        # control the FPR for each cascade lower than 0.5
        while F[i] > f * F[i - 1] or D[i] < d * D[i - 1]:
        
            n[i] += 1 # increase the number of features in the strong classifer

            print("\ntraining the strong classifier in each cascade ...")
            # train classifier using AdaBoost
            classifier = ab.learn(pos_train, neg_train, n[i], 
                min_feature_width, max_feature_width, min_feature_height, max_feature_height, verbose=True)
            print("\n...done\tvalidating the strong classifier on the development set ...")

            # test classifier performance on the development set
            TP, FN, FP, TN = utils.count_Rate(pos_dev_int_imgs, neg_dev_int_imgs, classifier)
            print("\nstatistics for this strong classifier as follows\nTP: %d\tFN: %d\tFP: %d\tTN: %d" % (TP, FN, FP, TN))
            
            D[i] = TP / (TP + FN) # update TPR
            F[i] = FP / (FP + TN) # update FPR

        neg_train = test_previous_cascade_classifier(neg_train_int_imgs, cascaded_classifiers)
        
        # stages are added until the overall target for false positive and detection rate is met
        cascaded_classifiers.append(classifier)

    return cascaded_classifier


def test_previous_cascade_classifier(neg_test_int_imgs, list_classifiers):
    # return all the misclassified images to decrease the FPR

    new_neg_imgs = list()

    for test_imgs in neg_test_int_imgs:
        for classifier in list_classifiers:
            if utils.ensemble_vote(neg_test_int_imgs, classifier) == 0:
                new_neg_imgs.append(test_imgs)

    return new_neg_imgs


def test_cascade_classifier(pos_test_int_imgs, neg_test_int_imgs, cascade, fp=-1):
    # para cascade: cascaded classifier
    # type cascade: list[list[haar.HaarLikeFeature]]
    # para fp: number of false positives
    # check the cascaded classifier

    pre_pos, rej_pos, pre_neg, rej_neg = 0, 0, 0, 0

    TP, FN, FP, TN = pre_pos, rej_pos, pre_neg, rej_neg

    fp = np.array((range(11)))*10 if fp != -1 else []

    detected_pos, detected_neg = False, False

    for i in range(len(pos_test_int_imgs)):
        
        for classifier in cascade:
            if utils.ensemble_vote(pos_test_int_imgs[i], classifier) == 0:
                FN += 1
                detected_pos = True
                break
        TP += 1 if detected_pos else 0
    
        for classifier in cascade:
            if utils.ensemble_vote(neg_test_int_imgs[i], classifier) == 1:
                FP += 1 # FALSE POSITIVES
                detected_neg = True
                break
        TN += 1 if detected_neg else 0

        print("TP %d FN %d FP %d TN %d" % (TP, FN, FP, TN))

        detection_rate = TP/(TP+FN) if TP+FN != 0 else 0.0

        if FP in fp:
            print("detection rate: %f when false detections: %d" % (detection_rate, FP))