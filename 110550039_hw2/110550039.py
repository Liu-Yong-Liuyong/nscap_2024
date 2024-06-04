# -*- coding: utf-8 -*-

from setting import get_hosts, get_switches, get_links, get_ip, get_mac


class host:
    def __init__(self, name, ip, mac):
        self.name = name
        self.ip = ip
        self.mac = mac 
        self.port_to = None 
        self.arp_table = dict() # maps IP addresses to MAC addresses
    def add(self, node):
        self.port_to = node
    def show_table(self):
        for i in self.arp_table:
            print(f'{i} : {self.arp_table[i]}')
    def clear(self):
        # clear ARP table entries for this host
        self.arp_table.clear()
    def update_arp(self, ip, mac):
        # update ARP table with a new entry
        self.arp_table[ip] = mac
    def handle_packet(self, packet):
        if packet['type'] == 'arp' and packet['reply'] != 'arpreply':
            source_ip = packet['source_ip']
            source_mac = packet['source_mac']
            
            # Check if the destination IP matches its own IP address
            if packet['destination_ip'] == self.ip:
                # Send ARP reply to the source (h1)
                # Update ARP table
                self.update_arp(source_ip, source_mac)
                arp_reply = {'type': 'arp', 'source_ip': self.ip, 'source_mac': self.mac,
                             'destination_ip': source_ip, 'destination_mac': source_mac,
                             'reply': 'arpreply'} 
                arp_reply['incoming_port'] = self.name
                self.send(arp_reply)
            else:
                pass
        if packet['reply'] == 'arpreply':
            if packet['destination_ip'] == self.ip:
                source_ip = packet['source_ip']
                source_mac = packet['source_mac']
                self.update_arp(source_ip, source_mac)
                icmp_packet = {'type': 'icmp', 'source_ip': self.ip, 'destination_ip': source_ip, 'destination_mac': source_mac, 'reply': 'ping_icmp'}
                icmp_packet['incoming_port'] = self.name
                self.send(icmp_packet)
        if packet['type'] == 'icmp' and packet['reply'] != 'icmpreply':
            if packet['destination_ip'] == self.ip:
                source_ip = packet['source_ip']
                source_mac = packet['source_mac']
                self.update_arp(source_ip, source_mac)#
                icmp_packet = {'type': 'icmp', 'source_ip': self.ip, 'destination_ip': source_ip, 'destination_mac': source_mac, 'reply': 'icmpreply'}
                icmp_packet['incoming_port'] = self.name
                self.send(icmp_packet)
        if packet['reply'] == 'icmpreply':
            if packet['destination_ip'] == self.ip:
                pass
               

    def ping(self, dst_ip):  
        # handle a ping request
        if dst_ip in self.arp_table:
            # Send ICMP request to the destination
            icmp_packet = {'type': 'icmp', 'source_ip': self.ip, 'destination_ip': dst_ip, 'reply': 'ping_icmp'}
            self.send(icmp_packet)
        else:
            # Broadcast ARP request to all hosts
            arp_packet = {'type': 'arp', 'source_ip': self.ip, 'destination_ip': dst_ip,'reply': 'ping_arp'}
            self.send(arp_packet) # for h1

    def send(self, packet):
        # determine the destination MAC here
        '''
            Hint :
                if the packet is the type of arp request, destination MAC would be 'ffff'.
                else, check up the arp table.
        '''
        # Determine the destination MAC address and send the packet
        if packet['type'] == 'arp' and packet['reply'] != 'arpreply':
            destination_mac = 'ffff'  # Broadcast MAC address
        else:
            destination_mac = self.arp_table.get(packet['destination_ip'], None)

        # Create a packet with source and destination MAC addresses
        packet['source_mac'] = self.mac
        packet['destination_mac'] = destination_mac

        node = self.port_to  # Get node connected to this host
        
        packet['incoming_port'] = self.name
        node.handle_packet(packet)

class switch:
    def __init__(self, name, port_n):
        self.name = name
        self.mac_table = dict() # maps MAC addresses to port numbers
        self.port_n = port_n # number of ports on this switch
        self.port_to = list() 
    def add(self, node): # link with other hosts or switches
        self.port_to.append(node)
    def show_table(self):
        for m in self.mac_table:
            print(f'{m} : {self.mac_table[m]}')
    def clear(self):
        # clear MAC table entries for this switch
        self.mac_table.clear()
    def update_mac(self, mac, port):
        # update MAC table with a new entry
        self.mac_table[mac] = port
    def send(self, idx, packet): # send to the specified port
        node = self.port_to[idx] 
        node.handle_packet(packet)  # Pass the incoming port index 
    def handle_packet(self, packet):  
        # handle incoming packets
        # Extract source MAC address from the packet
        source_mac = packet['source_mac']
        # Update MAC table with the source MAC address of the packet and the incoming port number
        count = 0
        for i in self.port_to:
            if i.name == packet['incoming_port']: #s1
                break
            count += 1
        incoming_port = count #count = 0
        self.update_mac(source_mac, incoming_port) #h1mac 0 for s2  #h1mac 2 for s1
        #print(self.mac_table[source_mac])
        '''
        if source_mac in self.mac_table and (self.mac_table[source_mac] < incoming_port):
            self.mac_table[source_mac] = self.mac_table[source_mac]
        else:
            self.update_mac(source_mac, incoming_port) #h1mac 0 for s2  #h1mac 2 for s1
        '''
        # Check if the destination MAC address is 'ffff'
        if packet['destination_mac'] == 'ffff':
            # Flood the packet out of all ports other than the incoming port
            for i, port in enumerate(self.port_to):
                if i != incoming_port:
                    packet['incoming_port'] = self.name
                    self.send(i, packet)
        else:
            destination_mac = packet['destination_mac']
            # Check if the MAC address of the destination host is in the MAC table
            if destination_mac in self.mac_table: 
                # Send the packet out of the port associated with the destination MAC address
                if incoming_port != self.mac_table[destination_mac]:
                    packet['incoming_port'] = self.name 
                    self.send(self.mac_table[destination_mac], packet)
            else:
                # Flood the packet by sending it on every port except the incoming one
                for i, port in enumerate(self.port_to):
                    if i != incoming_port:
                        packet['incoming_port'] = self.name
                        self.send(i, packet)

             

def add_link(tmp1, tmp2): # create a link between two nodes
    if tmp1 in host_dict:
        node1 = host_dict[tmp1]
    else:
        node1 =  switch_dict[tmp1]
    if tmp2 in host_dict:
        node2 = host_dict[tmp2]
    else:
        node2 = switch_dict[tmp2]
    node1.add(node2)

def set_topology():
    global host_dict, switch_dict
    hostlist = get_hosts().split(' ')
    switchlist = get_switches().split(' ')
    link_command = get_links()
    ip_dic = get_ip()
    mac_dic = get_mac()
    
    host_dict = dict() # maps host names to host objects
    switch_dict = dict() # maps switch names to switch objects
    
    for h in hostlist:
        host_dict[h] = host(h, ip_dic[h], mac_dic[h])
    for s in switchlist:
        switch_dict[s] = switch(s, len(link_command.split(s))-1)
    for l in link_command.split(' '):
        [n0, n1] = l.split(',')
        add_link(n0, n1)
        add_link(n1, n0)

def ping(tmp1, tmp2): # initiate a ping between two hosts
    global host_dict, switch_dict
    if tmp1 in host_dict and tmp2 in host_dict : 
        node1 = host_dict[tmp1]
        node2 = host_dict[tmp2]
        node1.ping(node2.ip)
    else : 
        return 1 # wrong 
    return 0 # success 


def show_table(tmp): # display the ARP or MAC table of a node
    if tmp == 'all_hosts':
        print(f'ip : mac')
        for h in host_dict:
            print(f'---------------{h}:')
            host_dict[h].show_table()
        print()
    elif tmp == 'all_switches':
        print(f'mac : port')
        for s in switch_dict:
            print(f'---------------{s}:')
            switch_dict[s].show_table()
        print()
    elif tmp in host_dict:
        print(f'ip : mac\n---------------{tmp}')
        host_dict[tmp].show_table()
    elif tmp in switch_dict:
        print(f'mac : port\n---------------{tmp}')
        switch_dict[tmp].show_table()
    else:
        return 1
    return 0


def clear(tmp):
    wrong = 0
    if tmp in host_dict:
        host_dict[tmp].clear()
    elif tmp in switch_dict:
        switch_dict[tmp].clear()
    else:
        wrong = 1
    return wrong


def run_net():
    while(1):
        wrong = 0 
        command_line = input(">> ")
        command_list = command_line.strip().split(' ')
        
        if command_line.strip() =='exit':
            return 0
        if len(command_list) == 2 : 
            if command_list[0] == 'show_table':
                wrong = show_table(command_list[1])
            elif command_list[0] == 'clear' :
                wrong = clear(command_list[1])
            else :
                wrong = 1 
        elif len(command_list) == 3 and command_list[1] == 'ping' :
            wrong = ping(command_list[0], command_list[2])
        else : 
            wrong = 1
        if wrong == 1:
            print('a wrong command')

    
def main():
    set_topology()
    run_net()


if __name__ == '__main__':
    main()