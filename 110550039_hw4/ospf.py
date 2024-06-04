import sys
import time
import socket
import select
import heapq
import json

'''
class Packet:
    def __init__(self, packet_type, source_router_id, destination_router_id, data):
        self.packet_type = packet_type
        self.source_router_id = source_router_id
        self.destination_router_id = destination_router_id
        self.data = data
'''
class NeighborState:
    DOWN = "DOWN"
    INIT = "INIT"
    EXCHANGE = "EXCHANGE"
    FULL = "FULL"

class LSA:
    def __init__(self, router_id, sequence_number, links,update_time):
        self.router_id = router_id #int
        self.sequence_number = sequence_number #int
        self.links = links
        self.update_time = update_time  # add update time attribute

    def to_dict(self):
        return {
            "router_id": self.router_id,
            "sequence_number": self.sequence_number,
            "links": self.links,
            "update_time": self.update_time  # include update time in the dictionary
        }
    def __str__(self):
        return f"LSA(router_id={self.router_id}, sequence_number={self.sequence_number}, links={self.links}), update_time={self.update_time})"

class Router:
    def __init__(self, router_id):
        self.router_id = router_id
        self.neighbor_table = {}
        self.routing_table = {}
        self.update_time = time.time()  # Initialize update time
        self.LSA = LSA(self.router_id, 0 , {}, self.update_time)  # Initialize self.LSA
        self.lsdb = {router_id: self.LSA}  # Initialize LSDB with self LSA # router_id is int
        self.lsa_sequence_number = 0
        self.lsa_refresh_interval = 15  # seconds
        self.lsa_timeout_interval = 30  # seconds
        self.lsa_timeout_queue = []
        self.adjacency_matrix = {}

    def updateTime_LSA(self,current_time):
        if (current_time - self.update_time) >= 15:
            mo_lsu = {}
            self.update_time = current_time
            self.lsa_sequence_number += 1
            links = {neighbor_id: neighbor_info["cost"] for neighbor_id, neighbor_info in self.neighbor_table.items()}
            lsa = LSA(self.router_id, self.lsa_sequence_number, links,current_time)
            self.LSA = lsa
            self.lsdb[self.router_id] = lsa
            mo_lsu[self.router_id] = lsa.to_dict()

            lsu_packet = json.dumps({"type": "LSU", "LSA": mo_lsu, "from_id":self.router_id, "timeout": "true"}).encode('utf-8')
            for neighbor_id,neighbor_info in self.neighbor_table.items():
                destination_port = 1000 + int(neighbor_id) # Adjust port number as needed
                self.send_packet(lsu_packet, destination_port)

    def check_lsa_timeout(self,current_time):
        for router_id in list(self.lsdb.keys()):
            lsa = self.lsdb[router_id]
            if (current_time - lsa.update_time) >= 30:
                print(f"{time.strftime('%H-%M-%S')} - remove LSA {lsa.router_id} {lsa.sequence_number}")
                del self.lsdb[router_id]
                

    def update_lsa(self):
        mo_lsu = {}
        update_time = time.time()
        self.update_time = time.time() #####
        links = {neighbor_id: neighbor_info["cost"] for neighbor_id, neighbor_info in self.neighbor_table.items()}
        self.lsa_sequence_number += 1
        lsa = LSA(self.router_id, self.lsa_sequence_number, links,update_time)
        self.LSA = lsa
        self.lsdb[self.router_id] = lsa

        mo_lsu[self.router_id] = lsa.to_dict()

        
        #self.lsa_timeout_queue.append((self.router_id, time.time() + self.lsa_timeout_interval))
        print(f"{time.strftime('%H-%M-%S')} - update LSA {lsa.router_id} {lsa.sequence_number}")

        lsu_packet = json.dumps({"type": "LSU", "LSA": mo_lsu, "from_id": self.router_id, "timeout":"false"}).encode('utf-8')
        for neighbor_id,neighbor_info in self.neighbor_table.items():
            destination_port = 1000 + int(neighbor_id) # Adjust port number as needed
            self.send_packet(lsu_packet, destination_port)

    def send_packet(self, packet_data, destination_port):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.sendto(packet_data, ('localhost', destination_port))


    def add_neighbor(self, neighbor_id, cost):
        self.neighbor_table[neighbor_id] = {"state": NeighborState.DOWN, "cost": cost, "dbd": None, "time": time.time(), "full_hello_recvtime" : 0} #增加dbd
        print(f"{time.strftime('%H-%M-%S')} - add neighbor {neighbor_id} {cost}")
        self.update_lsa()
        self.recalculate_routing_table()
        
    def update_neighbor(self, neighbor_id, cost):
        if neighbor_id in self.neighbor_table:
            self.neighbor_table[neighbor_id]["cost"] = cost
            print(f"{time.strftime('%H-%M-%S')} - update neighbor {neighbor_id} {cost}")
            self.update_lsa()
            self.recalculate_routing_table()

    def remove_neighbor(self, neighbor_id):
        if neighbor_id in self.neighbor_table:
            del self.neighbor_table[neighbor_id]
            print(f"{time.strftime('%H-%M-%S')} - remove neighbor {neighbor_id}")
            self.update_lsa()
            self.recalculate_routing_table()

    
    def process_ls_update(self, lsu):
        packet = json.loads(lsu.decode('utf-8'))
        lsas = packet["LSA"]
        lsu_flood = {}
        # Process received LSU
        if str(packet["from_id"]) in self.neighbor_table:
            for router_id, lsa_data in lsas.items(): #router_id is str
                lsa = LSA(int(router_id), lsa_data['sequence_number'], lsa_data['links'],lsa_data['update_time'])
                if int(router_id) not in self.lsdb: #因為router_id沒在self.lsdb裡，所以lsa可以直接指派
                    self.lsdb[int(router_id)] = lsa
                    print(f"{time.strftime('%H-%M-%S')} - add LSA {lsa.router_id} {lsa.sequence_number}")
                    lsu_flood[int(router_id)] = lsa.to_dict()
                elif int(router_id) in self.lsdb:
                    if lsa.sequence_number > self.lsdb[(lsa.router_id)].sequence_number:
                        self.lsdb[(lsa.router_id)] = lsa
                        if (lsa.router_id != self.router_id) and (packet["timeout"] == "false"):
                            print(f"{time.strftime('%H-%M-%S')} - update LSA {lsa.router_id} {lsa.sequence_number}")
                        lsu_flood[int(router_id)] = lsa.to_dict()
                    '''
                    If any LSAs in the LSDB are updated due to the received LSU, the router should flood the updated LSAs 
                    by containing them in an LSU and flooding the LSU.
                    '''
        if lsu_flood != {}:
                lsu_packet = json.dumps({"type": "LSU", "LSA": lsu_flood, "from_id": self.router_id,"timeout":packet["timeout"]}).encode('utf-8')
                for neighbor_id, neighbor_info in self.neighbor_table.items():
                    destination_port = 1000 + int(neighbor_id) # Adjust port number as needed
                    self.send_packet(lsu_packet, destination_port)

    def recalculate_routing_table(self):
        # Build adjacency matrix
        adjacency_matrix = {}
        #adjacency_matrix[0] = {}
        for router_id, lsa in self.lsdb.items():
            adjacency_matrix[router_id] = {}
            for neighbor_id, cost in lsa.links.items():
                adjacency_matrix[router_id][int(neighbor_id)] = cost
                
                if int(neighbor_id) not in adjacency_matrix:
                    adjacency_matrix[int(neighbor_id)] = {} # Initialize the inner dictionary for neighbor_id
                '''
                adjacency_matrix[int(neighbor_id)][router_id] = cost
                '''
        # Compute shortest paths/routes using Dijkstra's algorithm
        shortest_paths = self.dijkstra(adjacency_matrix, self.router_id)

        # Update routing table with shortest paths
        previous_routing_table = self.routing_table.copy()

        # Update routing table with shortest paths
        self.routing_table = shortest_paths
        '''
        keys_to_delete = []

        for destination_router_id, (next_hop_router_id, cost) in self.routing_table.items():
            if str(next_hop_router_id) not in self.neighbor_table:
                #print(next_hop_router_id)
                keys_to_delete.append(destination_router_id)

        # Delete the keys marked for deletion
        for key in keys_to_delete:
            print("key: ",key)
            if key in previous_routing_table:
                self.routing_table[key] = previous_routing_table[key]
            #del self.routing_table[key]
        '''
        current_time = time.strftime('%H-%M-%S')
        for destination_router_id, (next_hop_router_id, cost) in self.routing_table.items():
                if destination_router_id not in previous_routing_table:
                    print(f"{current_time} - add route {destination_router_id} {next_hop_router_id} {cost}")
                elif previous_routing_table[destination_router_id] != (next_hop_router_id, cost):
                    print(f"{current_time} - update route {destination_router_id} {next_hop_router_id} {cost}")

        # Check for removed routes 這裡要改EXIT的時候是不是也要REMOVE?
        for destination_router_id in previous_routing_table.keys():
            if destination_router_id not in self.routing_table:
                print(f"{current_time} - remove route {destination_router_id}")
   

    def send_message_to(self,destination_router_id,message):
        text_message = json.dumps({"type":"text","destination": destination_router_id,"message": message,"original":self.router_id}).encode('utf-8')
        if int(destination_router_id) in self.routing_table:
            next_hop_router_id, cost = self.routing_table[int(destination_router_id)]
            destination_port = 1000 + int(next_hop_router_id) # Adjust port number as needed
            self.send_packet(text_message, destination_port)
            
    
    def receive_text(self,data):
        packet = json.loads(data.decode('utf-8'))
        message = packet["message"]
        original = packet["original"]
        destination = packet["destination"]
        if int(destination) == self.router_id:
            #print("Recv message from ", original,":", message)
            print(f"Recv message from {original}: {message}")
        else:
            if int(destination) in self.routing_table:
                next_hop_router_id, cost = self.routing_table[int(destination)]
                destination_port = 1000 + int(next_hop_router_id) # Adjust port number as needed
                self.send_packet(data, destination_port)
                #print("Forward message from ", original," to ",destination,":", message)
                print(f"Forward message from {original} to {destination}: {message}")

        
    def dijkstra(self, graph, start):
        distances = {node: float('inf') for node in graph}
        previous_nodes = {node: None for node in graph}
        distances[start] = 0
        priority_queue = [(0, start)]

        while priority_queue:
            current_distance, current_node = heapq.heappop(priority_queue)

            if current_distance > distances[current_node]:
                continue

            for neighbor, weight in graph[current_node].items():
                distance = current_distance + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous_nodes[neighbor] = current_node
                    heapq.heappush(priority_queue, (distance, neighbor))

        # Construct the routing table
        routing_table = {}
        for destination_router_id in graph.keys():
            if destination_router_id != start:
                path = []
                next_hop_router_id = destination_router_id
                while next_hop_router_id is not None:
                    path.append(next_hop_router_id)
                    next_hop_router_id = previous_nodes[next_hop_router_id]
                path.reverse()
                next_hop_router_id = path[1] if len(path) > 1 else None
                if next_hop_router_id != None:
                    routing_table[destination_router_id] = (next_hop_router_id, distances[destination_router_id])

        return routing_table
        
        

class OSPFRouter:
    def __init__(self, router_id):
        self.router = Router(router_id)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Change to UDP socket
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('localhost', 1000 + router_id))
        self.inputs = [self.server_socket]

    def process_command(self, command):
        parts = command.split()
        if parts[0] == "addlink":
            neighbor_id = parts[1]
            cost = int(parts[2])
            self.router.add_neighbor(neighbor_id, cost)
        elif parts[0] == "setlink":
            neighbor_id = parts[1]
            cost = int(parts[2])
            self.router.update_neighbor(neighbor_id, cost)
        elif parts[0] == "rmlink":
            neighbor_id = parts[1]
            self.router.remove_neighbor(neighbor_id)
        elif parts[0] == "send":
            destination_router_id = parts[1]
            message = " ".join(parts[2:])
            self.send_message(destination_router_id, message)
        elif parts[0] == "exit":
            exit()

    def send_message(self, destination_router_id, message):
        self.router.send_message_to(destination_router_id,message)

    
    def receive_ls_update(self, lsu):
        self.router.process_ls_update(lsu)
        self.router.recalculate_routing_table()

    def handle_client_message(self, data):
        packet = json.loads(data.decode('utf-8'))
        if packet:
            if packet['type'] == "LSU":
                self.receive_ls_update(data)
            elif packet['type'] == "hello":
                self.receive_hello_message(data)
            elif packet['type'] == "dbd":
                self.receive_dbd(data)
            elif packet['type'] == "lsr":
                self.receive_lsr(data)
            else:
                self.router.receive_text(data)
            
    def send_hello_messages(self,prev_time):
        current_time = time.time()
        if (current_time - prev_time) >=1:
            for neighbor_id,neighbor_info  in self.router.neighbor_table.items():
                if self.router.neighbor_table[neighbor_id]["state"] == NeighborState.DOWN:#and int(neighbor_id) > self.router.router_id
                    hello_message = {
                        "type": "hello",
                        "from": self.router.router_id,
                        "to": neighbor_id,
                        "neighbor_state": NeighborState.DOWN,
                        "receive_hello":"false",
                        "be_neighbor_time":self.router.neighbor_table[neighbor_id]["time"]
                    }
                    packet = json.dumps(hello_message).encode('utf-8')
                    self.server_socket.sendto(packet, ('localhost', 1000 + int(neighbor_id)))
                elif self.router.neighbor_table[neighbor_id]["state"] == NeighborState.INIT:
                    hello_message = {
                        "type": "hello",
                        "from": self.router.router_id,
                        "to": neighbor_id,
                        "neighbor_state": NeighborState.INIT,
                        "receive_hello":"true"
                    }
                    packet = json.dumps(hello_message).encode('utf-8')
                    self.server_socket.sendto(packet, ('localhost', 1000 + int(neighbor_id)))
                elif self.router.neighbor_table[neighbor_id]["state"] == NeighborState.EXCHANGE:
                    hello_message = {
                        "type": "hello",
                        "from": self.router.router_id,
                        "to": neighbor_id,
                        "neighbor_state": NeighborState.EXCHANGE,
                        "receive_hello":"true"
                    }
                    packet = json.dumps(hello_message).encode('utf-8')
                    self.server_socket.sendto(packet, ('localhost', 1000 + int(neighbor_id)))
                elif self.router.neighbor_table[neighbor_id]["state"] == NeighborState.FULL:
                    hello_message = {
                        "type": "hello",
                        "from": self.router.router_id,
                        "to": neighbor_id,
                        "neighbor_state": NeighborState.FULL,
                        "receive_hello":"true"
                    }
                    packet = json.dumps(hello_message).encode('utf-8')
                    self.server_socket.sendto(packet, ('localhost', 1000 + int(neighbor_id)))
            prev_time = current_time

            for neighbor_id,neighbor_info  in self.router.neighbor_table.items():
                if self.router.neighbor_table[neighbor_id]["state"] == NeighborState.FULL and self.router.neighbor_table[neighbor_id]["full_hello_recvtime"] != 0:
                    last_recvhello_time = self.router.neighbor_table[neighbor_id]["full_hello_recvtime"]
                    current_time = time.time()
                    if (current_time - last_recvhello_time) >= 4:
                        self.router.neighbor_table[neighbor_id]["state"] = NeighborState.DOWN
                        self.router.neighbor_table[neighbor_id]["full_hello_recvtime"] = 0
                        if str(self.router.router_id) in self.router.lsdb[int(neighbor_id)].links:#####
                            #print(f"{time.strftime('%H-%M-%S')} -", "set neighbor state ", neighbor_id, " DOWN")
                            print(f"{time.strftime('%H-%M-%S')} - set neighbor state {neighbor_id} Down")
        return prev_time
    def receive_hello_message(self,hello_data):
        packet = json.loads(hello_data.decode('utf-8'))
        for neighbor_id,neighbor_info  in self.router.neighbor_table.items():
            if str(packet["from"]) == neighbor_id:
                if self.router.neighbor_table[neighbor_id]["state"] == NeighborState.DOWN and packet["receive_hello"]=="false" and packet["be_neighbor_time"] < self.router.neighbor_table[neighbor_id]["time"]:
                    self.router.neighbor_table[neighbor_id]["state"] = NeighborState.INIT
                    #print(f"{time.strftime('%H-%M-%S')} -", "set neighbor state ", neighbor_id, " INIT")
                    print(f"{time.strftime('%H-%M-%S')} - set neighbor state {neighbor_id} Init")
                elif self.router.neighbor_table[neighbor_id]["state"] == NeighborState.DOWN and packet["receive_hello"]=="true":
                    self.router.neighbor_table[neighbor_id]["state"] = NeighborState.EXCHANGE
                    #print(f"{time.strftime('%H-%M-%S')} -", "set neighbor state ", neighbor_id, " EXCHANGE")
                    print(f"{time.strftime('%H-%M-%S')} - set neighbor state {neighbor_id} Exchange")
                elif self.router.neighbor_table[neighbor_id]["state"] == NeighborState.INIT and packet["receive_hello"]=="true":
                    self.router.neighbor_table[neighbor_id]["state"] = NeighborState.EXCHANGE
                    #print(f"{time.strftime('%H-%M-%S')} -", "set neighbor state ", neighbor_id, " EXCHANGE")
                    print(f"{time.strftime('%H-%M-%S')} - set neighbor state {neighbor_id} Exchange")
                elif self.router.neighbor_table[neighbor_id]["state"] == NeighborState.FULL and packet["neighbor_state"] == NeighborState.FULL:
                    self.router.neighbor_table[neighbor_id]["full_hello_recvtime"] = time.time()
        '''
        for neighbor_id,neighbor_info  in self.router.neighbor_table.items():
            if self.router.neighbor_table[neighbor_id]["state"] == NeighborState.FULL and self.router.neighbor_table[neighbor_id]["full_hello_recvtime"] != 0:
                last_recvhello_time = self.router.neighbor_table[neighbor_id]["full_hello_recvtime"]
                current_time = time.time()
                if (current_time - last_recvhello_time) >= 4:
                    self.router.neighbor_table[neighbor_id]["state"] = NeighborState.DOWN
                    self.router.neighbor_table[neighbor_id]["full_hello_recvtime"] = 0
                    if str(self.router.router_id) in self.router.lsdb[int(neighbor_id)].links:#####
                        print(f"{time.strftime('%H-%M-%S')} -", "set neighbor state ", neighbor_id, " DOWN")
        '''
    def send_dbd(self,prev_time1):
        current_time = time.time()
        
        if current_time-prev_time1 >= 1:
            for neighbor_id,neighbor_info  in self.router.neighbor_table.items():
                #--------------------------------------------------------------full的時候也要送吧?
                self.before_send_dbd()
                if self.router.neighbor_table[neighbor_id]["state"] == NeighborState.EXCHANGE or self.router.neighbor_table[neighbor_id]["state"] == NeighborState.FULL:
                    lsdb_dict = {}
                    for router_id, lsa in self.router.lsdb.items():
                        lsdb_dict[router_id] = lsa.to_dict()
                    lsa_datas = lsdb_dict
                    dbd_packet = {
                        "type": "dbd",
                        "from": self.router.router_id,
                        "to": neighbor_id,
                        "router_id": self.router.router_id,
                        "sequence_number": self.router.lsdb[self.router.router_id].sequence_number,
                        "lsas": lsa_datas
                    }
                    packet = json.dumps(dbd_packet).encode('utf-8')
                    self.server_socket.sendto(packet, ('localhost', 1000 + int(neighbor_id)))
        prev_time1 = current_time
        return prev_time1
    def before_send_dbd(self):
        same = True
        for neighbor_id, info in self.router.neighbor_table.items():
            if (self.router.neighbor_table[neighbor_id]["state"] == NeighborState.EXCHANGE) and (self.router.neighbor_table[neighbor_id]["dbd"] != None):
                dbd_lsas = info["dbd"]["lsas"]
                local_lsas = self.router.lsdb
                if len(dbd_lsas) != len(local_lsas):
                    # If lengths are different, they are not the same
                    same = False

                # Check each LSA in DBD against local LSAs
                for router_id, dbd_lsa_data in dbd_lsas.items():
                    if int(router_id) not in local_lsas:
                        # If router_id not in local LSAs, they are different
                        same = False
                    local_lsa = local_lsas[int(router_id)]
                    if dbd_lsa_data["sequence_number"] != local_lsa.sequence_number:
                        # If sequence numbers are different, they are different
                        same = False
                if same:
                    self.router.neighbor_table[neighbor_id]["state"] = NeighborState.FULL
                    #print(f"{time.strftime('%H-%M-%S')} -", "set neighbor state ", neighbor_id, " FULL")
                    print(f"{time.strftime('%H-%M-%S')} - set neighbor state {neighbor_id} Full")
                else:
                    same = True
                
                
    def receive_dbd(self, dbd_packet): #remove link 會有問題
        packet = json.loads(dbd_packet.decode('utf-8'))
        #if self.router.neighbor_table[str(packet["from"])]["state"] == NeighborState.EXCHANGE or self.router.neighbor_table[str(packet["from"])]["state"] == NeighborState.FULL:
        #----------------------------------------------------------------- store dbd in neighbor_table
        neighbor_id = packet["from"]
        if str(neighbor_id) in self.router.neighbor_table:
            self.router.neighbor_table[str(neighbor_id)]["dbd"] = packet
        #-----------------------------------------------------------------
        receive_lsas = packet["lsas"]
        difference = []
        for router_id,lsa_data in receive_lsas.items():
            lsa = LSA(lsa_data["router_id"], lsa_data['sequence_number'], lsa_data['links'],lsa_data['update_time'])
            receive_sq = lsa.sequence_number
            if int(router_id) not in self.router.lsdb:
                difference.append(int(router_id))
            elif receive_sq < self.router.lsdb[int(router_id)].sequence_number:
                difference.append(router_id)
            else:
                receive_links = lsa.links
                current_links = self.router.lsdb[int(router_id)].links
                if receive_links != current_links:
                    difference.append(int(router_id))
        if not difference:
            set_router_id_full = packet["from"]
            if str(set_router_id_full) in self.router.neighbor_table: #####
                if self.router.neighbor_table[str(set_router_id_full)]["state"] == NeighborState.EXCHANGE:
                    self.router.neighbor_table[str(set_router_id_full)]["state"] = NeighborState.FULL
                    #print(f"{time.strftime('%H-%M-%S')} -", "set neighbor state ", neighbor_id, " FULL")
                    print(f"{time.strftime('%H-%M-%S')} - set neighbor state {neighbor_id} Full")
        else:
            send_to_id = packet["from"]
            lsr_packet = {
                "type": "lsr",
                "from": self.router.router_id,
                "to": send_to_id,  # int
                "diff_lsas_id": difference
            }
            packet = json.dumps(lsr_packet).encode('utf-8')
            self.server_socket.sendto(packet, ('localhost', 1000 + send_to_id))
            
    def receive_lsr(self,lsr_packet):
        packet = json.loads(lsr_packet.decode('utf-8'))
        lost_lsas = packet["diff_lsas_id"]
        lsu_packet = {}
        for id in lost_lsas:
            if id in self.router.lsdb:
                lsu_packet[id] = self.router.lsdb[id].to_dict()
        send_to_id = packet["from"]
        packet = json.dumps({"type": "LSU", "LSA": lsu_packet,"from_id":self.router.router_id,"timeout":"false"}).encode('utf-8')
        self.server_socket.sendto(packet, ('localhost', 1000 + send_to_id))

    def update_time(self,current_time):
        self.router.updateTime_LSA(current_time)
        self.router.check_lsa_timeout(current_time)
        

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 ospf.py <Router_ID>")
        sys.exit(1)

    router_id = int(sys.argv[1])
    ospf_router = OSPFRouter(router_id)
    #ospf_router.simulate_network()
    prev_time = time.time()
    prev_time1 = time.time()
    
    try:
        while True:
            current_time = time.time()
            # Check for incoming client messages or user commands
            read_sockets, _, _ = select.select(ospf_router.inputs + [sys.stdin], [], [], 1)
            ospf_router.update_time(current_time)
            
            prev_time = ospf_router.send_hello_messages(prev_time)
            prev_time1 = ospf_router.send_dbd(prev_time1)
            for sock in read_sockets:
                if sock == ospf_router.server_socket:
                    data, _ = ospf_router.server_socket.recvfrom(1024)  # Receive packet from neighbor
                    ospf_router.handle_client_message(data)
                elif sock == sys.stdin:
                    # Handle user input
                    command = input()
                    ospf_router.process_command(command)
            
    except KeyboardInterrupt:
        print("Exiting...")
