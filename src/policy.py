import numpy as np
import random 
import util
import pdb

### By default,  IGNORE_BID_ASK is False, only when the buyer bid is larger that the client ask
#   the client can be selected by this task.
#   NOTE: the client number of a task may not satisfy the required client number
IGNORE_BID_ASK = False

def buyer_give_more_money(client_idx, task_idx, price_table, bid_table):
    if IGNORE_BID_ASK:
        return True
    ### client ask
    buyer_bid = bid_table[client_idx][task_idx]
    seller_ask = price_table[client_idx][task_idx]
    return buyer_bid >= seller_ask

def mcafee_condition(client_idx, task_idx, price_table, buyer_bid):
    if IGNORE_BID_ASK:
        return True
    ### client ask
    seller_ask = price_table[client_idx][task_idx]
    return buyer_bid >= seller_ask

def select_one_client(client_idx, selected_client_index, free_client, _task):
    ### Return True if one task's requirement is satisfied
    selected_client_index.append(client_idx)
    free_client[client_idx] = False
    return len(selected_client_index) >= _task.required_client_num

def check_trade_success_or_not(selected_client_index, _task, free_client,update= True):
    if len(selected_client_index) < _task.required_client_num:
        ### Trade failed
        for client_idx in selected_client_index:
            free_client[client_idx] = True
        if update:
            _task.selected_client_idx = None
            _task.init_select_clients()
        return False
    else:
        ### Successful trade
        if update:
            _task.selected_client_idx = selected_client_index
            # print("Clients {} are assined to task {}".format(selected_client_index, _task.task_id))
            _task.init_select_clients()
        return True

def my_select_clients(ask_table, client_feature_list, task_list, bid_table):
    ''' client_feature_list: list
            a list of (cost, idlecost)
        task_list: list
            a list of class: Task
        bid_table: numpy array
            shape = (client_num, task_num)
    '''
    ### policy
    

    ### shape of task_bid_list = (task_num)
    task_bid_list = np.sum(bid_table, axis=0)

    sorted_task_with_index = sorted(enumerate(task_bid_list), key=lambda x: x[1], reverse=True)
    free_client = [True] * len(client_feature_list)
    succ_cnt = 0
    for task_idx, _ in sorted_task_with_index:
        _task = task_list[task_idx]
        
        client_value_for_this_task = [client_value_list[task_idx] for client_value_list in ask_table]
        client_value_list_sorted = sorted(enumerate(client_value_for_this_task), key=lambda x: x[1], reverse=True)

        ### Select clients
        selected_client_index = []
        for client_idx, _ in client_value_list_sorted:
            if free_client[client_idx] :
            # and buyer_give_more_money(client_idx, task_idx, ask_table, bid_table):
                is_task_ready = select_one_client(client_idx, selected_client_index, free_client, _task)
                if is_task_ready:
                    break
        
        is_succ = check_trade_success_or_not(selected_client_index, _task, free_client)
        if is_succ:
            succ_cnt += _task.required_client_num
    
    return succ_cnt, None


def mcafee_select_clients(ask_table, client_feature_list, task_list, bid_table, update= True):
    ''' client_feature_list: list
            a list of (cost, idlecost)
        task_list: list
            a list of class: Task
        bid_table: numpy array
            shape = (client_num, task_num)
    '''

    ### policy

    ### shape of task_bid_list = (task_num)
    task_bid_list = np.sum(bid_table, axis=0)-3.5
    sorted_task_with_index = sorted(enumerate(task_bid_list), key=lambda x: x[1], reverse=True)
    client_value_list =  np.sum((ask_table), axis=1)
    client_value_list_sorted = sorted(enumerate(client_value_list), key=lambda x: x[1], reverse=False)
    client_num= len(client_value_list)
    task_num = len(task_bid_list)
    print("mb", sorted_task_with_index)
    print("ma",client_value_list_sorted)
    print("task#: ", task_num, " client#: ", client_num)

    i = 0
    free_client = [True] * len(client_feature_list)
    succ_cnt = 0
    while i < task_num-1:
        task_id = sorted_task_with_index[i][0]
        _task = task_list[task_id]
        # print(task_id, _task.task_id, _task.required_client_num)
        trade_succed = False
        assert client_num > 0
        
        j = 0
        selected_client_index = []
        while j < (client_num-1):
            client_id = client_value_list_sorted[j][0]

            has_post_client = False
            next_idx = 1
            while (j+next_idx) < client_num:
                next_client_id = client_value_list_sorted[j+next_idx][0]
                if free_client[next_client_id]:
                    has_post_client = True
                    break
                next_idx += 1

            if has_post_client:
                check = free_client[client_id] and sorted_task_with_index[i][1] >= client_value_list_sorted[j][1] \
                    and sorted_task_with_index[i][1] < client_value_list_sorted[j+next_idx][1]
            else:
                check = False

            if check:
                is_task_ready = select_one_client(client_id, selected_client_index, free_client, _task)
                ### check whether the requirement of this taks has been met
                if is_task_ready:
                    # raise NotImplementedError("Remove this task away")
                    trade_succed = True
                    break
                j = 0
                continue
            j += 1
        if not trade_succed:
            for client_idx in selected_client_index:
                free_client[client_idx] = True
            if update:
                _task.selected_client_idx = None
            # raise ValueError("Fail trading")
        else:
            ### end of client selection for one task
            trade_succed = check_trade_success_or_not(selected_client_index, _task, free_client, update = update)

        ### Cacluate reward  and count successful matching
        reward = 0
        if trade_succed:
            refer_bid = task_list[i+1].bid_per_loss_delta
            

            tmp = 0

            for client_idx in selected_client_index:
                refer_ask = util.sigmoid(client_value_list[client_idx+1])
                tmp += (refer_bid + refer_ask) / 2

                print("p",refer_ask)
                
            
            reward += tmp * _task.total_loss_delta *100
              
            ### count successful matching
            succ_cnt += _task.required_client_num
            
        i += 1
    

    ### Note: the last task can absolutely not trade successfully
    if update:
        task_id = sorted_task_with_index[task_num-1][0]
        _task = task_list[task_id]
        _task.selected_client_idx = None

    return succ_cnt, reward

    ### The original mecafee algorithm
    # while task_num > 0:
    #     assert client_num > 0
    #     trade_succed = False
    #     for k in range(min(client_num, task_num) - 1):
    #         if sorted_task_with_index[k][1] >= client_value_list_sorted[k][1] \
    #             and sorted_task_with_index[k+1][1] < client_value_list_sorted[k+1][1]:
    #             task_id = sorted_task_with_index[k][0]
    #             client_id = client_value_list_sorted[k][0]
    #             task_list[task_id].selected_client_idx.append(client_id)
    #             # raise NotImplementedError("Remove this client away")
    #             client_value_list_sorted.pop(k)
    #             client_num -= 1

    #             ### check whether the requirement of this taks has been met
    #             if len(task_list[task_id].selected_client_idx) == task_list[task_id].required_client_num:
    #                 # raise NotImplementedError("Remove this task away")
    #                 sorted_task_with_index.pop(k)
    #                 task_num -= 1
                
    #             trade_succed = True
    #             break
    #     if not trade_succed:
    #         raise ValueError("Fail trading")

def simple_select_clients(num_of_client, task_list, reverse=False):
    free_client = [True] * num_of_client
    succ_cnt = 0

    task_list[0].selected_client_idx = [1, 5]
    task_list[1].selected_client_idx = [2, 4]
    # print("Clients {} are assined to task {}".format(selected_client_index, _task.task_id))
    task_list[0].init_select_clients()
    task_list[1].init_select_clients()


    # for task_idx, _ in enumerate(task_list):
    #     _task = task_list[task_idx]

    #     ### Select clients
    #     selected_client_index = []
    #     iterator = range(num_of_client)
    #     if reverse:
    #         iterator = reversed(iterator)
    #     for client_idx in iterator:
    #         if free_client[client_idx]:
    #             # and buyer_give_more_money(client_idx, task_idx, ask_table, bid_table):
    #             is_task_ready = select_one_client(client_idx, selected_client_index, free_client, _task)
    #             if is_task_ready:
    #                 break
    #     is_succ = check_trade_success_or_not(selected_client_index, _task, free_client)
    #     if is_succ:
    #         succ_cnt += _task.required_client_num
    return succ_cnt, None

def random_select_clients(num_of_client, task_list):
    free_client = [True] * num_of_client
    succ_cnt = 0
    for task_idx, _ in enumerate(task_list):
        _task = task_list[task_idx]
       
        ### Select clients
        selected_client_index = []
        clients_candidates = list(range(num_of_client))
        while len(clients_candidates) > 0:
            client_idx= random.choice(clients_candidates)
            clients_candidates.remove(client_idx)
            if free_client[client_idx] :
            # and buyer_give_more_money(client_idx, task_idx, ask_table, bid_table):
                is_task_ready = select_one_client(client_idx, selected_client_index, free_client, _task)
                if is_task_ready:
                    break
        
        is_succ = check_trade_success_or_not(selected_client_index, _task, free_client)
        if is_succ:
            succ_cnt += _task.required_client_num
    return succ_cnt, None

def even_select_clients(ask_table, client_feature_list, task_list, bid_table, update=True):
    num_of_client = len(client_feature_list)
    free_client = [True] * num_of_client
    succ_cnt = 0
    reward = 0
    task_bid_list = np.sum(bid_table, axis=0)-5
    for task_idx, _ in enumerate(task_list):
        _task = task_list[task_idx]
       
        ### Select clients
        selected_client_index = []
        clients_candidates = list(range(num_of_client))
        while len(clients_candidates) > 0:
            client_idx= random.choice(clients_candidates)
            clients_candidates.remove(client_idx)
            if free_client[client_idx] and buyer_give_more_money(client_idx, task_idx, ask_table, bid_table):
                is_task_ready = select_one_client(client_idx, selected_client_index, free_client, _task)
                if is_task_ready:
                    break
        
        is_succ = check_trade_success_or_not(selected_client_index, _task, free_client, update = update)
        if is_succ:
            succ_cnt += _task.required_client_num
            ### Cacluate reward  and count successful matching
            refer_bid = task_bid_list[task_idx]
            for client_idx in selected_client_index:
                reward += refer_bid / len(selected_client_index)

    return succ_cnt, reward

def momentum_select_clients(num_of_client, task_list):
    # pdb.set_trace()
    free_client = [True] * num_of_client
    succ_cnt = 0
    # import pdb; pdb.set_trace()
    for task_idx, _ in enumerate(task_list):
        _task = task_list[task_idx]

        _task.update_proj_list()

        ### momemtum_based_grad_proj 是一个list，长度等于 总的client数量，挑出momemtum_based_grad_proj最小的num_users client
        # 这里client_state 不需要传参了， 因为client_state在这个函数定义之前就已经定义了，函数内部可以直接访问client_state 
        momemtum_based_grad_proj = _task.client_state.client2proj
        # print("Proj", momemtum_based_grad_proj)
        assert isinstance(momemtum_based_grad_proj, list) or isinstance(momemtum_based_grad_proj, np.ndarray)
        assert len(momemtum_based_grad_proj) == num_of_client

        alpha = 0.1
        momemtum_based_grad_proj = np.array(momemtum_based_grad_proj)
        ucb = momemtum_based_grad_proj + alpha * np.sqrt((2 * np.log(_task.cient_update_cnt))/_task.client_state.client2selected_cnt)
        # print("ucb", ucb)
        sorted_client_idxs = ucb.argsort()[::-1]

        ### Select clients
        selected_client_index = []
        for client_idx in sorted_client_idxs:
            if free_client[client_idx] :
                # and buyer_give_more_money(client_idx, task_idx, ask_table, bid_table):
                is_task_ready = select_one_client(client_idx, selected_client_index, free_client, _task)
                if is_task_ready:
                    break
                
        is_succ = check_trade_success_or_not(selected_client_index, _task, free_client)
        if is_succ:
            succ_cnt += _task.required_client_num
    return succ_cnt, None