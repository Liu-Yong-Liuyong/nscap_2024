import sys
import time
import socket
import select
import json
import queue
import random
import threading

class Host:
    def __init__(self, host_id):
        self.host_id = host_id
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(('localhost', 5000 + host_id))
        self.inputs = [self.server_socket]
        self.transmitting = False
        self.other_status = {self.host_id: False}
        self.send_queue = queue.Queue()
        self.copy_queue = queue.Queue()#5/14
        self.current_dest = 0
        self.heard_cts = False
        self.last_backoff_time = 0
        self.backoff_timer = 0 
        self.last_status_broadcast_time = 0
        self.last_collision_detect_time = 0 #5/14
        self.backoff_thread = None  # Initialize backoff thread
        self.status_changed_event = threading.Event()  # Event to signal status change
        self.collision = 0#5/14


    def send_packet(self, destination_id, packet):
        destination_address = ('localhost', 5000 + destination_id)
        self.server_socket.sendto(packet, destination_address)
    #可能要改成由bs轉傳
    def broadcast_transmitting_status(self):
        current_time = time.time()
        if current_time - self.last_status_broadcast_time >= 1:  # Broadcast once per second
            self.last_status_broadcast_time = current_time
            for dest_id in range(1, 5):  # Assuming there are 4 hosts in total, adjust as needed
                packet = {'type': 'STATUS', 'source': self.host_id, 'destination': dest_id, 'transmitting': self.transmitting}
                if dest_id != self.host_id:
                    #self.send_packet(dest_id, json.dumps(packet).encode())
                    self.send_packet(0, json.dumps(packet).encode()) #send to BS
    def check_medium_idle(self):
        return all(value == False for key, value in self.other_status.items() if (key != self.host_id and key != 4))#5/14
    
    #5/14------------------------------------------------------------------------------------------
    def collision_detect(self):
        if self.host_id != 4:
            current_time = time.time()
            if (current_time - self.last_collision_detect_time) >=1:
                #print(self.other_status)
                self.last_collision_detect_time = current_time
                true_count = sum(1 for value in self.other_status.values() if value)
                true_keys = [key for key, value in self.other_status.items() if value]
                if true_count >= 2 and self.host_id in true_keys:
                    print("----------Collision Happened.----------")
                    self.collision = 1
                    self.transmitting = False
                    self.other_status[self.host_id] = False
                    self.broadcast_transmitting_status()
                    time.sleep(1)
       
                    
    def handle_data(self, data):
        packet = json.loads(data.decode())
        if packet['type'] == 'RTS':
            #print(f"Host {self.host_id} received RTS from Host {packet['source']}")
            print(f"BS received RTS from Host {packet['source']}")
            # BS傳給sender
            #self.send_packet(packet['source'], json.dumps({'type': 'CTS', 'source': self.host_id, 'destination': packet['source']}).encode())
            for dest_id in range(1, 5):#5/15
                self.send_packet(dest_id, json.dumps({'type': 'CTS', 'source': self.host_id, 'destination': packet['source']}).encode())
            
        elif packet['type'] == 'CTS':
            if packet['destination'] == self.host_id :
                #print(f"Host {self.host_id} received CTS from Host {packet['source']}")
                print(f"Host {self.host_id} received CTS from BS")
                if self.send_queue.qsize() > 0:#5/14
                    destination_id, data = self.send_queue.get()
                else:
                    destination_id, data = self.copy_queue.get()
                packet = {'type': 'DATA', 'source': self.host_id, 'destination': destination_id, 'data': data}
                self.send_packet(destination_id, json.dumps(packet).encode())
            #else:#5/15
                #print(f"Host {self.host_id} received CTS from BS")
        #-------------------------------------------------------------------------------------------------------------------------
        elif packet['type'] == 'DATA':
            if self.host_id == packet['destination']:
                print(f"Host {self.host_id} received DATA from Host {packet['source']}")
                time.sleep(5)#SIFS time
                self.send_packet(0, json.dumps({'type': 'ACK', 'source': self.host_id, 'destination': packet['source']}).encode()) #將ack送給BS
        elif packet['type'] == 'ACK':
            if self.host_id == packet['destination'] and self.collision == 0: #5/14
                print(f"Host {self.host_id} received ACK from Host {packet['source']}")
                self.transmitting = False
                self.other_status[self.host_id] = False
                self.broadcast_transmitting_status()
            elif self.host_id == 0:
                self.send_packet(packet['destination'], json.dumps(packet).encode())
            elif self.collision == 1:#5/14
                self.collision = 0
                self.backoff_thread = threading.Thread(target=self.handle_backoff, args=(self.current_dest,))
                self.backoff_thread.start()
        elif packet['type'] == 'STATUS':
            if self.host_id == 0:
                self.send_packet(packet['destination'], json.dumps(packet).encode()) #send to BS
            else:
                host_id = packet['source']
                self.other_status[host_id] = packet['transmitting']
                self.status_changed_event.set()  # Signal that status has changed
#-----------------------------------------------------------------------
    def handle_backoff(self, destination_id):
        print("----------Start Random Backoff Timer.----------")
        self.backoff_timer = random.randint(7, 10)
        if self.last_backoff_time == 0:
            self.last_backoff_time = self.backoff_timer
        if self.backoff_timer < self.last_backoff_time:
            self.backoff_timer = (self.last_backoff_time + 1)
        self.continue_backoff(destination_id)
    def continue_backoff(self,destination_id):
        if self.backoff_timer > 0:  # If countdown not finished
            if self.check_medium_idle():
                print("Remain Time: ", self.backoff_timer)
                time.sleep(1)  # Simulated slot time
                self.backoff_timer -= 1
                self.continue_backoff(destination_id)  # Continue counting down
            else:
                print("----------Medium Is Busy. Backoff Paused.----------")
                self.pause_backoff(destination_id)
        else:
            print("----------Backoff Countdown Finished. Try Sending Packet.----------")
            if self.check_medium_idle():
                time.sleep(3)#DIFS time
                if self.check_medium_idle():
                    packet = {'type': 'RTS', 'source': self.host_id, 'destination': destination_id}
                    self.transmitting = True
                    self.other_status[self.host_id] = True
                    self.broadcast_transmitting_status()
                    self.send_packet(0, json.dumps(packet).encode()) #指定0為BS
                else:
                    self.backoff_thread = threading.Thread(target=self.handle_backoff, args=(destination_id,))
                    self.backoff_thread.start()
            else:
                self.backoff_thread = threading.Thread(target=self.handle_backoff, args=(destination_id,))
                self.backoff_thread.start()
               

    def pause_backoff(self,destination_id):
        while not self.check_medium_idle():
            #print(self.other_status)
            time.sleep(1)  # Check medium state periodically
            self.status_changed_event.wait()  # Wait for status change event
            self.status_changed_event.clear()  # Clear the event
        print("----------Medium Become Idle. Resuming Backoff.----------")
        self.continue_backoff(destination_id)  # Resume counting down
#------------------------------------------------------------------------
    def process_command(self, command):
        parts = command.split(' ')
        if parts[0].lower() == 'send' and len(parts) >= 3:
            if self.host_id == 4:#5/14
                if not self.check_medium_idle():
                    dest_id = int(parts[1])
                    data = ' '.join(parts[2:]) # Join all parts after the second part as data
                    self.send_queue.put((dest_id,data))
                    packet = {'type': 'RTS', 'source': self.host_id, 'destination': dest_id}
                    time.sleep(3) #DIFS time
                    self.transmitting = True
                    self.other_status[self.host_id] = True
                    self.broadcast_transmitting_status()
                    self.send_packet(0, json.dumps(packet).encode()) #指定0為BS

            elif self.check_medium_idle() :
                dest_id = int(parts[1])
                data = ' '.join(parts[2:]) # Join all parts after the second part as data
                self.send_queue.put((dest_id,data))
                self.copy_queue.put((dest_id,data))#5/14
                self.current_dest = dest_id#5/14
                packet = {'type': 'RTS', 'source': self.host_id, 'destination': dest_id}
                time.sleep(3) #DIFS time
                if self.check_medium_idle():
                    #self.send_packet(dest_id, json.dumps(packet).encode())
                    self.transmitting = True
                    self.other_status[self.host_id] = True
                    self.broadcast_transmitting_status()
                    self.send_packet(0, json.dumps(packet).encode()) #指定0為BS
                else:
                    self.backoff_thread = threading.Thread(target=self.handle_backoff, args=(dest_id,))
                    self.backoff_thread.start()
            else:
                # start backeoff
                dest_id = int(parts[1])
                data = ' '.join(parts[2:]) # Join all parts after the second part as data
                self.send_queue.put((dest_id,data))
                self.backoff_thread = threading.Thread(target=self.handle_backoff, args=(dest_id,))
                self.backoff_thread.start()
        else:
            print("Invalid command")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 csmaca.py <host_ID>")
        sys.exit(1)

    host_id = int(sys.argv[1])
    host = Host(host_id)
    host.last_status_broadcast_time = time.time()
    host.last_collision_detect_time = time.time()
    try:
        while True:
            current_time = time.time()
            read_sockets, _, _ = select.select(host.inputs + [sys.stdin], [], [], 1)
            host.broadcast_transmitting_status()
            host.collision_detect()
            for sock in read_sockets:
                if sock == host.server_socket:
                    data, _ = host.server_socket.recvfrom(1024)  # Receive packet from neighbor
                    host.handle_data(data)
                elif sock == sys.stdin:
                    # Handle user input
                    command = input()
                    host.process_command(command)
            
    except KeyboardInterrupt:
        print("Exiting...")
