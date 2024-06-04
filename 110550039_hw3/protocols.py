import random

def initialize_hosts(setting,protocol):
    """Initialize hosts with default values."""
    hosts = []
    for i in range(setting.host_num):
        host = {
            "protocol": protocol,
            "id": i,                
            "status": 0,            # 0: standby, 1: send, 2: resend
            "action_to_do": 0,      # 0: standby, 1: send, 2: resend, 3: stop sending
            "packet_num": 0,   
            "remain_length": 0,     # remain time to sending
            "wait_time": 0,         # time wait to send
            "collision": False,
            "success_num": 0,
            "collision_num": 0,
            "history": "",          # record history of host's actions
        }
        hosts.append(host)
    return hosts

def generate_packets_times(setting):
    """
    Generate packets for each host.
    """
    packets_times = setting.gen_packets()
    return packets_times

def process_packet_generation(hosts, packets_times, t):
    """
    Process packet generation for each host at time t.
    """
    for h in hosts:
        if len(packets_times[h["id"]]) > 0 and packets_times[h["id"]][0] == t:
            packets_times[h["id"]].pop(0)
            h["packet_num"] += 1
    
    return hosts, packets_times

def perform_action(hosts,history,setting):
    """
    Perform actions for each host.
    """
    for h in hosts:
        if h["action_to_do"] == 3:  # stop sending
            h["collision"] = False
            h["remain_length"] = 0
            h["collision_num"] += 1
            h["wait_time"] = random.randint(0, setting.max_collision_wait_time)
            history[h["id"]] = "|"
            h["status"] = 0
        else:
            h["status"] = h["action_to_do"]
    return hosts,history

def check_collision_idle(sending_list, is_idle_time,total_idle_time,hosts,history):
    """
    Check for collisions and idle time.
    """
    for h in hosts:
        if h["status"] == 1:
            sending_list.append(h)
            is_idle_time = False
        if history[h["id"]] != ".":
            is_idle_time = False
                
    if len(sending_list) > 1:
        for h in sending_list:
            h["collision"] = True
    if is_idle_time:
        total_idle_time += 1
    return sending_list, is_idle_time, total_idle_time, hosts, history

def update_host_status(hosts,history,setting):
    """
    Update the status of hosts.
    """
    for h in hosts:
        if h["status"] == 1:
            if len(h["history"]) == 0 or (h["history"][-1] != "<" and h["history"][-1] != "-"):
                history[h["id"]] = "<"
            else:
                history[h["id"]] = "-"
            h["remain_length"] -= 1
            if h["remain_length"] <= 0:
                if h["collision"]:
                    if h["protocol"] == "slotted_aloha":
                        h["status"] = 2 # resend 
                    else:
                        h["wait_time"] = random.randint(0, setting.max_collision_wait_time)
                        h["status"] = 0 # standby
                    h["collision_num"] += 1
                    history[h["id"]] = "|"
                else:
                    h["status"] = 0
                    h["success_num"] += 1
                    h["packet_num"] -= 1
                    history[h["id"]] = ">"
                h["collision"] = False
        h["history"] += history[h["id"]]
    return hosts,history
def shows_history(packets_times, hosts, setting):
    """
    Show history of packet transmissions.
    """
    packets_times = setting.gen_packets()
    for h in hosts:
        s = ""
        for t in range(setting.total_time):
            if len(packets_times[h["id"]]) > 0 and packets_times[h["id"]][0] == t:
                s += "V"
                packets_times[h["id"]].pop(0)
            else:
                s += " "
        print(f"    {s}")
        print(f"h{h['id']}: {h['history']}")
    return packets_times,hosts




def aloha(setting, show_history=False):
    hosts = initialize_hosts(setting,"aloha")
    packets_times = generate_packets_times(setting) # Generate packets for each host
    total_idle_time = 0
    for t in range(setting.total_time):
        history = ["." for i in range(setting.host_num)]
        hosts,packets_times =process_packet_generation(hosts, packets_times, t) # Generate packets for each host
        for h in hosts:
            h["action_to_do"] = h["status"]
            if h["status"] == 0: # only need to check status is standby
                if h["wait_time"] > 0:
                    h["wait_time"] -= 1
                elif h["packet_num"] > 0:
                    h["action_to_do"] = 1
                    h["remain_length"] = setting.packet_time

        hosts,history = perform_action(hosts,history,setting)
        sending_list = []
        is_idle_time = True
        sending_list, is_idle_time, total_idle_time,hosts,history = check_collision_idle(sending_list, is_idle_time,total_idle_time,hosts,history)
        
        hosts,history = update_host_status(hosts,history,setting)
        
    if show_history:
        packets_times,hosts = shows_history(packets_times, hosts, setting)

    '''
    Calculate the success rate, idle rate, and collision rate  
    '''    
    total_success_num = 0
    for h in hosts:
        total_success_num += h["success_num"]
    total_success_time = total_success_num * setting.packet_time
    total_collision_time = setting.total_time - total_success_time - total_idle_time
    return (
        total_success_time / setting.total_time,
        total_idle_time / setting.total_time,
        total_collision_time / setting.total_time,
    )
    
    

def slotted_aloha(setting, show_history=False):
    hosts = initialize_hosts(setting,"slotted_aloha")
    packets_times = generate_packets_times(setting) # Generate packets for each host
    total_idle_time = 0
    for t in range(setting.total_time):
        history = ["." for i in range(setting.host_num)]
        hosts,packets_times =process_packet_generation(hosts, packets_times, t) # Generate packets for each host
        for h in hosts:
            h["action_to_do"] = h["status"]
            if h["status"] == 0:
                if h["wait_time"] > 0:
                    h["wait_time"] -= 1

                elif h["packet_num"] > 0 and t % setting.packet_time == 0:
                    h["action_to_do"] = 1       
                    h["remain_length"] = setting.packet_time

            elif h["status"] == 2 and t % setting.packet_time == 0:
                '''
                If a collision occurs, the host decides whether to retransmit the packet with probability p 
                at the beginning of each following time slot.
                '''
                r = random.random()
                if r < setting.p_resend:
                    h["action_to_do"] = 1
                    h["remain_length"] = setting.packet_time

        hosts,history = perform_action(hosts,history,setting)
        sending_list = []
        is_idle_time = True
        sending_list, is_idle_time, total_idle_time,hosts,history = check_collision_idle(sending_list, is_idle_time,total_idle_time,hosts,history)
        hosts,history = update_host_status(hosts,history,setting)
    if show_history:
        packets_times,hosts = shows_history(packets_times, hosts, setting)
    '''
    Calculate the success rate, idle rate, and collision rate  
    '''     
    total_success_num = 0
    for h in hosts:
        total_success_num += h["success_num"]
    total_success_time = total_success_num * setting.packet_time
    total_collision_time = setting.total_time - total_success_time - total_idle_time
    return (
        total_success_time / setting.total_time,
        total_idle_time / setting.total_time,
        total_collision_time / setting.total_time,
    )

def csma(setting, one_persistent=False, show_history=False):
    hosts = initialize_hosts(setting,"csma")
    packets_times = generate_packets_times(setting) # Generate packets for each host
    total_idle_time = 0
    for t in range(setting.total_time):
        history = ["." for i in range(setting.host_num)]
        hosts,packets_times =process_packet_generation(hosts, packets_times, t) # Generate packets for each host
        for h in hosts:
            h["action_to_do"] = h["status"]
            if h["status"] == 0: 
                if h["wait_time"] > 0:
                        h["wait_time"] -= 1
                elif h["packet_num"] > 0:
                    '''
                    All hosts detect if someone else is sending before starting to send
                    '''
                    others_sending = False
                    for others in hosts:
                        if others["id"] == h["id"]:
                            continue
                        if (setting.link_delay >= 0 and t > (setting.link_delay + 1) and ( others["history"][t - (setting.link_delay + 1)] == "-" or others["history"][t - (setting.link_delay + 1)] == "<")):
                            others_sending = True
                            
                    if not others_sending:
                        h["action_to_do"] = 1
                        h["remain_length"] = setting.packet_time
                    else:
                        if not one_persistent:
                            h["wait_time"] = random.randint(0, setting.max_collision_wait_time)

        hosts,history = perform_action(hosts,history,setting)
        sending_list = []
        is_idle_time = True
        sending_list, is_idle_time, total_idle_time,hosts,history = check_collision_idle(sending_list, is_idle_time,total_idle_time,hosts,history)
        hosts,history = update_host_status(hosts,history,setting)
    if show_history:
        packets_times,hosts = shows_history(packets_times, hosts, setting)
    '''
    Calculate the success rate, idle rate, and collision rate  
    '''     
    total_success_num = 0
    for h in hosts:
        total_success_num += h["success_num"]
    total_success_time = total_success_num * setting.packet_time
    total_collision_time = setting.total_time - total_success_time - total_idle_time
    return (
        total_success_time / setting.total_time,
        total_idle_time / setting.total_time,
        total_collision_time / setting.total_time,
    )

def csma_cd(setting, one_persistent=False, show_history=False):
    hosts = initialize_hosts(setting,"csma_cd")
    packets_times = generate_packets_times(setting) # Generate packets for each host
    total_idle_time = 0
    for t in range(setting.total_time):
        history = ["." for i in range(setting.host_num)]
        hosts,packets_times =process_packet_generation(hosts, packets_times, t) # Generate packets for each host
        for h in hosts:
            h["action_to_do"] = h["status"]
            
            if h["status"] == 0:
                if h["wait_time"] > 0:
                    h["wait_time"] -= 1

                elif h["packet_num"] > 0:
                    others_sending = False
                    for others in hosts:
                        if others["id"] == h["id"]:
                            continue
                        if (setting.link_delay >= 0 and t > (setting.link_delay + 1) and ( others["history"][t - (setting.link_delay + 1)] == "-" or others["history"][t - (setting.link_delay + 1)] == "<")):
                         others_sending = True
                        
                    if not others_sending:
                        h["action_to_do"] = 1
                        h["remain_length"] = setting.packet_time
                    else:
                        if not one_persistent:
                            h["wait_time"] = random.randint(0, setting.max_collision_wait_time)
            elif h["status"] == 1:
                '''
                The host continually detects collisions during transmission and 
                aborts the transmission if a collision is detected.
                '''
                others_sending = False
                for others in hosts:
                    if others["id"] == h["id"]:
                        continue
                    if (
                        setting.link_delay >= 0
                        and t > (setting.link_delay + 1)
                        and (
                            others["history"][t - (setting.link_delay + 1)] == "-"
                            or others["history"][t - (setting.link_delay + 1)] == "<"
                        )
                    ):
                        others_sending = True
                if others_sending:
                    h["action_to_do"] = 3

        hosts,history = perform_action(hosts,history,setting)
        sending_list = []
        is_idle_time = True
        sending_list, is_idle_time, total_idle_time,hosts,history = check_collision_idle(sending_list, is_idle_time,total_idle_time,hosts,history)
        hosts,history = update_host_status(hosts,history,setting)
    if show_history:
        packets_times,hosts = shows_history(packets_times, hosts, setting)
    '''
    Calculate the success rate, idle rate, and collision rate  
    '''    
    total_success_num = 0
    for h in hosts:
        total_success_num += h["success_num"]
    total_success_time = total_success_num * setting.packet_time
    total_collision_time = setting.total_time - total_success_time - total_idle_time
    return (
        total_success_time / setting.total_time,
        total_idle_time / setting.total_time,
        total_collision_time / setting.total_time,
    )