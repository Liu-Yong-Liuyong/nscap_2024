#include <arpa/inet.h> // inet_addr
#include <cstring>     // memcpy
#include <iostream>
#include <netinet/ether.h> // ethernet header struct
#include <netinet/ip.h>    // ip header struct
#include <netinet/udp.h>   // udp header struct
#include <pcap.h>          // pcap libary
#include <unistd.h>


#define MAX_PACKET_SIZE 65535
#define LOOPBACK_INTERFACE "lo" 

/* some useful identifiers:
 * - ETH_ALEN = 6   (ethernet address length)
 * - ETH_HLEN = 14	(ethernet header length)
*/

// TODO 5
void modify_mac_address(struct ether_header *eth_header) {
    // struct ether_header reference:
    // https://sites.uclouvain.be/SystInfo/usr/include/net/ethernet.h.html
    
    uint8_t src_mac[] = {0x08, 0x00, 0x12, 0x34, 0x56, 0x78};
    memcpy(eth_header->ether_shost, src_mac, ETH_ALEN);

  
    uint8_t dest_mac[] = {0x08, 0x00, 0x12, 0x34, 0xac, 0xc2};
    memcpy(eth_header->ether_dhost, dest_mac, ETH_ALEN);

    
}

// TODO 6
void modify_ip_address(struct ip *ip_header) {
     
    ip_header->ip_src.s_addr = inet_addr("10.1.1.3");

    ip_header->ip_dst.s_addr = inet_addr("10.1.1.4");
}

int main() {

    // TODO 1: Open the pcap file
    char errbuf[PCAP_ERRBUF_SIZE];

    pcap_t *handle = pcap_open_offline("test.pcap", errbuf);

    if (handle == NULL) {
        fprintf(stderr, "Error opening pcap file: %s\n", errbuf);
        return 1; // Return error code
    }

    // TODO 2: Open session with loopback interface "lo"
    pcap_t *send_handle = pcap_open_live(LOOPBACK_INTERFACE, BUFSIZ, 1, 1000, errbuf);

    if (send_handle == NULL) {
        fprintf(stderr, "Error opening loopback interface: %s\n", errbuf);
        pcap_close(handle); // Close the pcap file handle if opened
        return 1; // Return error code
    }


    struct pcap_pkthdr *header;
    const u_char *packet;

    // TODO 8: Variables to store the time difference between each packet
    struct timeval prev_time ;
    struct timeval current_time;

    // TODO 3: Loop through each packet in the pcap file
    int count = 0;
    while (pcap_next_ex(handle, &header, &packet) == 1) {

        struct timeval ts = header->ts;

        // Print timestamp in seconds and microseconds
        //std::cout << "Packet timestamp: " << ts.tv_sec << "." << ts.tv_usec << std::endl;
        current_time = ts;
        if(count == 0){
            prev_time=current_time;
        }

        // TODO 4: Send the original packet
        if (pcap_sendpacket(send_handle, packet, header->len) != 0) {
            fprintf(stderr, "Failed to send packet\n");
            continue; // Skip to the next packet if sending fails
        }
        

        // TODO 5: Modify mac address (function up above)
        struct ether_header *eth_header = (struct ether_header *)packet;
        modify_mac_address(eth_header);
        

        // TODO 6: Modify ip address if it is a IP packet (hint: ether_type)
        if (ntohs(eth_header->ether_type) == ETHERTYPE_IP) {
            // Assuming Ethernet headers
            struct ip *ip_header = (struct ip *)(packet + ETH_HLEN);
            modify_ip_address(ip_header);   // modify function up above
        }

        // TODO 8: Calculate the time difference between the current and the
        // previous packet and sleep. (hint: usleep)
        int time_diff = (current_time.tv_sec - prev_time.tv_sec) * 1000000 + (current_time.tv_usec - prev_time.tv_usec);
        //std::cout<<time_diff<<std::endl;
        usleep(time_diff);
        
        // TODO 7: Send the modified packet
        if (pcap_sendpacket(send_handle, packet, header->len) != 0) {
            fprintf(stderr, "Failed to send modified packet\n");
            continue;  // Skip to the next packet if sending fails
        }

        // TODO 8: Update the previous packet time
        prev_time = current_time;
        count++;
    }
    
    // Close the pcap file
    pcap_close(handle);
    pcap_close(send_handle);
    
    
    return 0;
}