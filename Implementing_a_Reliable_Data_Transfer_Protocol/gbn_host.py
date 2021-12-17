from network_simulator import NetworkSimulator, Packet, EventEntity
from enum import Enum
from struct import pack, unpack




class GBNHost():

    # The __init__ method accepts:
    # - a reference to the simulator object
    # - the value for this entity (EntityType.A or EntityType.B)
    # - the interval for this entity's timer
    # - the size of the window used for the Go-Back-N algorithm
    def __init__(self, simulator, entity, timer_interval, window_size):
        
        # These are important state values that you will need to use in your code
        self.simulator = simulator
        self.entity = entity
        
        # Sender properties
        self.timer_interval = timer_interval        # The duration the timer lasts before triggering
        self.window_size = window_size              # The size of the seq/ack window
        self.window_base = 0                        # The last ACKed packet. This starts at 0 because no packets 
                                                    # have been ACKed
        self.next_seq_num = 0                       # The SEQ number that will be used next
        self.unAcked_buffer = []
        self.app_layer_buffer = []

        self.exp_seq_num = 0
        self.last_ack_pkt = self.make_pkt(-1, "ACK")

    ###########################################################################################################
    ## Core Interface functions that are called by Simulator


    # This function implements the SENDING functionality. It should implement retransmit-on-timeout. 
    # Refer to the GBN sender flowchart for details about how this function should be implemented
    def receive_from_application_layer(self, payload):
        
        if self.next_seq_num < self.window_base + self.window_size:
            self.unAcked_buffer.append(self.make_pkt(self.next_seq_num, payload))
            self.simulator.pass_to_network_layer(self.entity, self.unAcked_buffer[self.next_seq_num], self.current_ack(self.unAcked_buffer[self.next_seq_num]))
            
            if(self.window_base == self.next_seq_num):
                self.simulator.start_timer(self.entity, self.timer_interval)
            self.next_seq_num += 1
        else:
            self.app_layer_buffer.append(payload)


    # This function implements the RECEIVING functionality. This function will be more complex that
    # receive_from_application_layer(), it includes functionality from both the GBN Sender and GBN receiver
    # FSM's (both of these have events that trigger on receive_from_network_layer). You will need to handle 
    # data differently depending on if it is a packet containing data, or if it is an ACK.
    # Refer to the GBN receiver flowchart for details about how to implement responding to data pkts, and
    # refer to the GBN sender flowchart for details about how to implement responidng to ACKs
    def receive_from_network_layer(self, byte_data):
        
        if self.current_ack(byte_data) and not self.is_corrupt(byte_data):
            acknum = self.get_currAck_num(byte_data)

            if acknum >= self.window_base:
                self.window_base = acknum + 1
                self.simulator.stop_timer(self.entity)

                if self.window_base != self.next_seq_num:
                    self.simulator.start_timer(self.entity, self.timer_interval)
                
                while len(self.app_layer_buffer) > 0 and self.next_seq_num < self.window_base + self.window_size:
                    payload = self.app_layer_buffer.pop()
                    self.unAcked_buffer.append(self.make_pkt(self.next_seq_num, payload))
                    self.simulator.pass_to_network_layer(self.entity, self.unAcked_buffer[self.next_seq_num], self.current_ack(self.unAcked_buffer[self.next_seq_num]))  
                    
                    if self.window_base == self.next_seq_num:
                        self.simulator.start_timer(self.entity, self.timer_interval)
                    self.next_seq_num += 1
            
        elif self.is_corrupt(byte_data):
            self.simulator.pass_to_network_layer(self.entity, self.last_ack_pkt, self.current_ack(self.last_ack_pkt)) 
        elif self.get_currSeq_num(byte_data) != self.exp_seq_num:
            self.simulator.pass_to_network_layer(self.entity, self.last_ack_pkt, self.current_ack(self.last_ack_pkt)) 
        else:
            try:
                data = self.payload_Ext(byte_data)
                   
            except Exception as e:
                self.simulator.pass_to_network_layer(self.entity, self.last_ack_pkt, self.current_ack(self.last_ack_pkt))
            self.simulator.pass_to_application_layer(self.entity, data)
            self.last_ack_pkt = self.make_pkt(self.exp_seq_num, "ACK")
            self.simulator.pass_to_network_layer(self.entity, self.last_ack_pkt, self.current_ack(self.last_ack_pkt)) 
            self.exp_seq_num += 1

                
        


    # This function is called by the simulator when a timer interrupt is triggered due to an ACK not being 
    # received in the expected time frame. All unACKed data should be resent, and the timer restarted
    def timer_interrupt(self):
        self.simulator.start_timer(self.entity, self.timer_interval)
        for num in range(self.window_base, self.next_seq_num, 1):
            self.simulator.pass_to_network_layer(self.entity, self.unAcked_buffer[num], self.current_ack(self.unAcked_buffer[num]))


    # This function should check to determine if a given packet is corrupt. The packet parameter accepted
    # by this function should contain a byte array
    def is_corrupt(self, packet):
        
        head = unpack("!HiHI", packet[:12])
        checksum = head[2]
        header = pack("!HiHI", head[0], head[1], 0, head[3])
        pkt = header + packet[12:]

        if checksum == self.cal_checksum(pkt):
            return False
        else:
            return True
        
    def cal_checksum(self, packet):        
        if len(packet) % 2 != 0:
            packet = packet + bytes(1)

        byte = 0x0000
        for i in range(0, len(packet), 2):
            word = packet[i] << 8 | packet[i+1]
            byte = byte + word
            byte = (byte & 0xffff) + (byte >> 16)
        byte = ~byte & 0xffff
        return byte

    def make_pkt(self, next_seq_num, payload):
        # Calculate the checksum
        # format for packet is "!HiHI"
        # The format listing: Pkt type, Pkt Num, Checksum, Payload
        if payload == "ACK":
            pkt = pack("!HiHI", 0, next_seq_num,0, 0)
            check_sum = self.cal_checksum(pkt)
            pkt = pack("!HiHI", 0, next_seq_num, check_sum, 0)
        else:
            pkt = pack("!HiHI%is"%len(payload), 128, next_seq_num, 0, len(payload), payload.encode())
            check_sum = self.cal_checksum(pkt)
            pkt = pack("!HiHI%is"%len(payload), 128, next_seq_num, check_sum, len(payload), payload.encode())
        return pkt


    def current_ack(self, pkt):
        head = unpack("!HiHI", pkt[:12])
        if head[0] == 0:
            return True
        else:
            return False

    def get_currAck_num(self, pkt):
        head = unpack("!HiHI", pkt[:12])
        return head[1]
    
    def get_currSeq_num(self, pkt):
        head = unpack("!HiHI", pkt[:12])
        return head[1]

    def payload_Ext(self, pkt):
        head = unpack("!HiHI", pkt[:12])
        data = unpack("!%is" % head[3], pkt[12:])
        return data[0].decode()
        
