from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import icmp


class ExampleSwitch13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ExampleSwitch13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Default table: send all packets to filter_table_1
        match = parser.OFPMatch()
        instructions = [parser.OFPInstructionGotoTable(1)]
        self.add_flow(datapath, 0, match, instructions, table_id=0)

        # Filter table 1: send ICMP packets to filter_table_2, others to forward_table
        match = parser.OFPMatch(eth_type=0x0800, ip_proto=1)  # IPv4 and ICMP
        instructions = [parser.OFPInstructionGotoTable(2)]
        self.add_flow(datapath, 1, match, instructions, table_id=1)
        # filter table 1, go to forward table
        match = parser.OFPMatch()
        instructions = [parser.OFPInstructionGotoTable(3)]
        self.add_flow(datapath, 0, match, instructions, table_id=1)

        # Filter table 2: drop ICMP packets from port 3 and port 4, forward others
        target_ports = [3, 4]
        for port in target_ports:
            match = parser.OFPMatch(in_port=port)
            instructions = []  # Drop packet
            self.add_flow(datapath, 1, match, instructions, table_id=2)
        # filter table 2, go to forward table
        match = parser.OFPMatch()
        instructions = [parser.OFPInstructionGotoTable(3)]
        self.add_flow(datapath, 0, match, instructions, table_id=2)

        # Forward table: forward packets
        match = parser.OFPMatch()
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, 
                        [parser.OFPActionOutput(ofproto.OFPP_NORMAL)])]
        self.add_flow(datapath, 0, match, instructions, table_id=3)

    def add_flow(self, datapath, priority, match, instructions, table_id=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=instructions,
                                table_id=table_id)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == 0x0800:
            ip = pkt.get_protocol(ipv4.ipv4)
            if ip.proto == 1:
                icmp_pkt = pkt.get_protocol(icmp.icmp)

        dst = eth.dst
        src = eth.src
        in_port = msg.match['in_port']

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)], table_id=3)

        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions,
                                  data=msg.data)
        datapath.send_msg(out)
