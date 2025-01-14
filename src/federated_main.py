#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Python version: 3.6

import os
import time
import numpy as np
import pandas as pd
import random
from datetime import datetime

from task import Task
import util

import torch
from torch.utils.tensorboard import SummaryWriter

from svfl import calculate_sv
from options import args_parser
from exp_utils import exp_details
import policy
from client import get_clients
from util import STEP_NUM, PRINT_EVERY

args = args_parser()

np.random.seed(1)
torch.manual_seed(0)
random.seed(0)

### Experiment Configsc
MIX_RATIO = 0.8
SIMULATE = False
EPOCH_NUM = 200
TRIAL_NUM = 1
TASK_NUM = 2

bid_per_loss_delta_space = [1]
required_client_num_space = os.environ.get("REQUIRE_CLIENT_NUM", None)
if required_client_num_space is None: 
    required_client_num_space = [2]
else:
    required_client_num_space = [int(x) for x in required_client_num_space.split("_")]
# target_labels_space = [[0,5],[1,4]]
# target_labels_space = [list(range(5)),list(range(5,10))]

# Init target label and the space for the required 
# distribution for the test dataset
if args.target_label == "identical":
    target_labels_space = [None]
    test_required_dist_space = [None]
elif args.target_label == "overlap":
    target_labels_space = [
        [1,4,5,3,6,9],
        [2,8,7,1,4,5]]
    test_required_dist_space = [
        [15,15,15,15,15,15],
        [15,15,15,15,15,15]]
elif args.target_label == "non_overlap":
    target_labels_space = [
        [3,6,9],
        [2,8,7]]
    test_required_dist_space = [
        [30,30,30],
        [30,30,30]]
else:
    raise ValueError()

if __name__ == '__main__':
    start_time = time.time()

    # define paths
    path_project = os.path.abspath('..')

    now = datetime.now() # current date and time
    logger = SummaryWriter(f'../logs/{now.strftime("%Y-%m-%d_%H:%M:%S")}-{args.policy}-{args.dataset}-iid={args.iid}-{args.model}-lr_{args.lr}')
    exp_details(args)
    
    train_dataset, test_client, all_clients = get_clients(args)
    ############################### Task ###########################################
    ### Initialize the global model parameters for both tasks
    ### At the first epoch, both tasks select all clients
    print("\nInitialize tasks ... ")
    task_list = []
    def create_task(selected_client_idx, required_client_num, bid_per_loss_delta,
            target_labels=None, test_required_dist=None):
        task = Task(args, start_time, logger, train_dataset, test_client, all_clients,
            task_id = len(task_list),
            selected_client_idx=selected_client_idx,
            required_client_num=required_client_num,
            bid_per_loss_delta=bid_per_loss_delta,
            target_labels=target_labels,
            test_required_dist=test_required_dist)
        # assert task.target_labels is not None, target_labels
        task_list.append(task)

    for task_id in range(TASK_NUM):
        create_task(
            selected_client_idx=list(range(args.num_users)),
            required_client_num=util.sample_config(required_client_num_space, task_id, use_random=False),
            bid_per_loss_delta=util.sample_config(bid_per_loss_delta_space, task_id, use_random=False),
            target_labels=util.sample_config(target_labels_space, task_id, use_random=False),
            test_required_dist=util.sample_config(test_required_dist_space, task_id, use_random=False)
        )
    ############################### Predefined structure for NmFLI ###########################################
    if args.policy == "nmfli" or "greedy":
        cost_list=[]
        for client_idx in range(args.num_users):
            # cost_list.append(random.randint(1,10)/10)
            cost_list.append(0)
        
        idlecost_list = []
        for client_idx in range(args.num_users):
            idlecost_list.append(0)

        client_feature_list = list(zip( cost_list, idlecost_list))
            
        ### Initialize the price_table and bid table
        price_table = None
        def init_price_table(price_table):
            # Price table, of shape (# of clients, # of tasks), 
            # where each element is a list of (epoch, value) pairs
            price_table = []
            for client_idx in range(args.num_users):
                init_price_list = []
                for taks_idx in range(len(task_list)):
                    init_price_list.append([])
                price_table.append(init_price_list)
            return price_table
        
        price_table = init_price_table(price_table)
        bid_table = np.zeros((args.num_users, len(task_list)))

    ############################### Main process of FL ##########################################
    print("\nStart training ...")
    for epoch in range(EPOCH_NUM):
        for task in task_list:
            task.epoch = epoch
        print()
        for round_idx in range(STEP_NUM):
            ### Train the model parameters distributedly
            for task in task_list:
                task.train_one_round()

        ### At the end of this epoch
        if (epoch+1) % PRINT_EVERY == 0: 
            if args.policy == "nmfli":
                shapely_value_table = [task.shap() for task in task_list]
                ### Normalize using sigmoid
                shapely_value_table = [
                    np.array(util.sigmoid(np.array(elem))) if len(elem) > 0 else np.array(elem) 
                        for elem in shapely_value_table]
                shapely_value_table = [arr / np.max(arr) for arr in shapely_value_table]
                # shapely_value_table = np.array(shapely_value_table)
                # shapely_value_table /= np.expand_dims(np.max(shapely_value_table, axis=1), axis=1)
                if args.verbose:
                    util.pretty_print_2darray("Shap Table [task\\client]", shapely_value_table)

                ### Update price table
                for task_idx in range(len(task_list)):
                    if task_list[task_idx].selected_client_idx is None:
                        continue
                    selected_client_index = task_list[task_idx].selected_client_idx
                    for idx in range(len(selected_client_index)):
                        client_idx = selected_client_index[idx]
                        shapely_value_scaled = shapely_value_table[task_idx][idx]
                        # shapely_value_scaled = shapley_value * len(selected_client_index) / args.num_users
                        # price_table[client_idx][task_idx] = ((epoch / (epoch + 1)) * price_table[client_idx][task_idx] \
                        #     + (1 / (epoch + 1)) * shapely_value_scaled)
                        # price_table[client_idx][task_idx] = shapely_value_scaled
                        price_table[client_idx][task_idx].append((epoch, shapely_value_scaled, task_list[task_idx].delta_accu))
                
                total_cost = 0
                bid_list = [task.delta_accu * task.bid_per_loss_delta for task in task_list]
                total_bid = sum(bid_list)
            
                for task in task_list:
                    if task.selected_client_idx is None:
                        continue
                    for client_idx in task.selected_client_idx :
                        total_cost += cost_list[client_idx]

                assert price_table is not None
            
                ### Update bid table
                for task_idx in range(len(task_list)):
                    if task_list[task_idx].selected_client_idx is None:
                        continue
                    selected_client_index = task_list[task_idx].selected_client_idx
                    for idx in range(len(selected_client_index)):
                        client_idx = selected_client_index[idx]
                        shapley_value = shapely_value_table[task_idx][idx]
                        bid_table[client_idx][task_idx] = shapley_value * bid_list[task_idx]

            ###select clients for all tasks
            if args.policy == "random":
                succ_cnt, reward = policy.random_select_clients(args.num_users, task_list)
            elif args.policy == "momentum":
                succ_cnt, reward = policy.momentum_select_clients(args.num_users, task_list)
                # if use_all_users == True :
                #     idxs_users = momemtum_based(args.num_users)
                # else:
                #     idxs_users = momemtum_based(m)
            elif args.policy == "simple":
                succ_cnt, reward = policy.simple_select_clients(args.num_users, task_list)
            elif args.policy == "simple_reverse":
                succ_cnt, reward = policy.simple_select_clients(args.num_users, task_list, reverse=True)
            elif args.policy == "size":
                succ_cnt, reward = policy.datasize_select_clients(args.num_users,task_list)
            elif args.policy == "afl":
                succ_cnt, reward = policy.AFL_select_clients(args.num_users, task_list)
            elif args.policy == "greedy":
                norm_bid_table = util.normalize_data(bid_table)
                succ_cnt, reward = policy.greedy_select_clients(args.num_users, task_list, norm_bid_table)
            elif args.policy == "nmfli":
                if args.verbose:
                    util.pretty_print_2darray("Price Table [client\\task]", price_table)
                ask_table = util.calcualte_client_value(price_table, client_feature_list)
                if args.verbose:
                    util.pretty_print_2darray("Ask Table [client\\task]", ask_table)
                norm_ask_table = util.normalize_data(ask_table)
                norm_bid_table = util.normalize_data(bid_table)
                succ_cnt, reward = policy.my_select_clients(
                        norm_ask_table,
                        client_feature_list,
                        task_list,
                        norm_bid_table)
                # if use_all_users == True :
                #     idxs_users = shap_based(args.num_users)
                # else:
                #     idxs_users = shap_based(m)
            elif args.policy == "debug":
                idxs_users = np.array(list(range(args.num_users)))[:m]
            else:
                raise ValueError(f"Invalid policy {args.policy}")

            for task in task_list:
                task.end_of_epoch()

    # Cache results
    header = ["Step"]
    all_data = []
    for task_id, task in enumerate(task_list):
        header.extend([f"Task {task_id} time", f"Task {task_id} train loss",
                       f"Task {task_id} test accu."])
        if task_id == 0:
            all_data.append(task.epoch_num)
        else:
            assert task.epoch_num == all_data[0]
        
        all_data.append(task.timestamp)
        all_data.append(task.train_loss)
        all_data.append(task.test_accuracy)
    
    all_data = np.array(all_data).T
    df = pd.DataFrame(all_data, columns=header)
    cache_path = os.environ.get("NMFLI_EXP_NAME", f"save/result/{args.dataset}-{args.target_label}-{args.model}-"
        f"{args.policy}") + ".csv"
    if not os.path.exists(os.path.dirname(cache_path)):
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    df.to_csv(cache_path, index=False)
    
    ### Previous method to perform shap-based client selection
    # def shap_based(num_users):
        
    #     ''' shap_based_grad_proj 是一个list，长度等于 总的client数量，挑出shap_based_grad_proj最大的num_users client
    #     '''
    #     sv = client_state.sv
    #     shap_based_grad_proj = np.array(sv)
    #     return shap_based_grad_proj.argsort()[-num_users:]

    # elif args.policy == "nmfli":
    #     if epoch == 0:
    #         client2weights = dict([(idxs_users[i], local_weights[i]) for i in range(len(idxs_users))])
    #         print(f"Calculate shaple value for {len(idxs_users)} clients")
    #         sv = calculate_sv(client2weights, evaluate_model, fed_avg)
    #         client_state.sv=sv
    #         idxs_users = update_client_idx(use_all_users=False)
            
    # PLOTTING (optional)
    # import matplotlib
    # import matplotlib.pyplot as plt
    # matplotlib.use('Agg')

    # Plot Loss curve
    # plt.figure()
    # plt.title('Training Loss vs Communication rounds')
    # plt.plot(range(len(train_loss)), train_loss, color='r')
    # plt.ylabel('Training loss')
    # plt.xlabel('Communication Rounds')
    # plt.savefig('../save/fed_{}_{}_{}_C[{}]_iid[{}]_E[{}]_B[{}]_loss.png'.
    #             format(args.dataset, args.model, args.epochs, args.frac,
    #                    args.iid, args.local_ep, args.local_bs))
    #
    # # Plot Average Accuracy vs Communication rounds
    # plt.figure()
    # plt.title('Average Accuracy vs Communication rounds')
    # plt.plot(range(len(train_accuracy)), train_accuracy, color='k')
    # plt.ylabel('Average Accuracy')
    # plt.xlabel('Communication Rounds')
    # plt.savefig('../save/fed_{}_{}_{}_C[{}]_iid[{}]_E[{}]_B[{}]_acc.png'.
    #             format(args.dataset, args.model, args.epochs, args.frac,
    #                    args.iid, args.local_ep, args.local_bs))
