from ChatMessageParser import *
from socket import *
import os, sys
import selectors
import logging



# When you first register a socket with your selector (except for the server socket), you'll want to
# place an instance of ConnectionData into the data field. ConnectionData will keep track of our
# write buffer for a given socket. When you want to send a message across a socket, add it to the write
# buffer in the ConnectionData object associated with the socket. This can then be read once you call 
# select() on your selector and confirm that a socket is ready to be written to.
class ConnectionData(object):
    def __init__(self):
        self.write_buffer = b''


# When your server socket creates a new socket during the accept() call, you do not know if the entity
# on the other side is a server or a client. You will learn this when you receive either a
# ServerRegistration or ClientRegistration message. Once you have received a registration message, you will
# want to replace the socket's associated ConnectionData object with either a ServerData or ClientData object.
# You can do this using the modify() function of your selector (more information is provided in the comments
# for the registration handler functions).
# ServerData extends ConnectionData with properties specific to a connection with a server and ClientData
# extends ConnectionData with properties specific to a connection with a client. As the both extend 
# ConnectionData, both also contain the write_buffer property.
class ServerData(ConnectionData):
    def __init__(self, id, server_name, server_info):
        super(ServerData, self).__init__()
        self.id = id
        self.server_name = server_name     # Stores the name of the server
        self.server_info = server_info     # Stores a human-readable description of the server
        self.first_link_id = None          # The ID of the first host on the path to this server

class ClientData(ConnectionData):    
    def __init__(self, id, client_name, client_info):
        super(ClientData, self).__init__()
        self.id = id
        self.client_name = client_name      # Stores the name of the client
        self.client_info = client_info      # Stores a human-readable description of the client
        self.first_link_id = None           # The ID of the first host on the path to this client


class CRCServer(object):

    # Initialization method
    def __init__(self, options, run_on_localhost=False):

        # TODO: Create your selector and store it in self.sel
        self.sel = selectors.DefaultSelector()


        # The following three variables define important properties of this server. Their values are
        # populated based on the options value passed into the constructor. Do not change the contents
        # of these variables
        # -----------------------------------------------------------------------------
        # The numeric ID of this server
        self.id = options.id
        # The name of this server
        self.server_name = options.servername
        # The human-readable information about this server
        self.server_info = options.info


        # The following four variables will be used to track information about the state of the network
        # -----------------------------------------------------------------------------
        # You will create an instance of ServerData or ClientData whenever receiving a registration 
        # message. In addition to updating the socket's associated ConnectionData object, you should also
        # store the new ServerData or ClientData object in the hosts_db dictionary. This will allow you to
        # access information about all known hosts on the network whenever you need it. The key for a given
        # ServerData or ClientData object should be set to the id number of that Server or Client.
        self.hosts_db = {}

        # This list should contain the ids of all servers that are directly connected to this server.
        self.adjacent_server_ids = []

        # This list should contain the ids of all clients that are directly connected to this server 
        self.adjacent_user_ids = []
        
        # Store the content of all status messages directed to this server in this list. This is purely 
        # for grading purposes
        self.status_updates_log = []


        # The following three variables define important configuration information about this server's
        # connection to the wider network. Their values are populated based on the options value passed 
        # into the constructor. Do not change the contents of these variables
        # -----------------------------------------------------------------------------
        # The port that you should listen for new connections on (e.g. the port your server socket listens to)
        self.port = options.port

         # Except for the first server to start, all other servers must connect to an existing server in 
         # order to join the network. The name of the server that this server should connect to is defined here.
         # If this value is blank, then this server is the first to be started.
        self.connect_to_host = options.connect_to_host

        # The IP address of the server to connect to on startup. Since we're testing everything locally, this is
        # just set to our loopback IP address. 
        self.connect_to_host_addr = '127.0.0.1'
    
        # The port that the server we're connecting to is listening on for new connection requests.
        self.connect_to_port = options.connect_to_port


        # This dictionary contains mappings from commands to command handlers. When you receive a message, you can
        # find the appropriate message handler by using the message type code as the key for the dictionary.
        #   e.g. self.message_handlers[0x00] will return a reference to the handle_server_registration_message.
        # Once you have the reference to the function, you can call it just like if you had typed the function name 
        # directly. E.g. self.message_handlers[0x01](io_device, msg) will call the function and pass in io_device and msg
        # -----------------------------------------------------------------------------
        self.message_handlers = {
            # Message handlers
            0x00:self.handle_server_registration_message,
            0x01:self.handle_status_message,
            0x80:self.handle_client_registration_message,
            0x81:self.handle_client_chat_message,
            0x82:self.handle_client_quit_message,
        }


        # The following variables configuring logging for this application
        # -----------------------------------------------------------------------------
        self.log_file = options.log_file
        self.logger = None
        self.init_logging()


        # Request_terminate will be set to True by the CRCTestManager when it is ready for the server to shutdown.
        # DO NOT CHANGE THE CONTENTS OF THIS VARIBLE YOURSELF
        # -----------------------------------------------------------------------------
        self.request_terminate = False



    # DO NOT EDIT THIS METHOD. This will be called by the CRCTestManager to start your server
    # Setup the server and start listening for incoming messages
    def run(self):
        self.print_info("Launching server %s..." % self.server_name)

        # Set up the server socket that will listen for new connections
        self.setup_server_socket()

        # If we are supposed to connect to another server on startup, then do so now
        if self.connect_to_host and self.connect_to_port:
            self.connect_to_server()
        
        # Begin listening for connections on the server socket
        self.check_IO_devices_for_messages()
        



    ###############################################################################################################
    ###############################################################################################################
    ## You will need to complete this block of functions to pass the first three basic Connection tests
    ##

    # This function is responsible for setting up the server socket and registering it with your selector
    # TODO: Create a TCP server socket and bind to self.port (defined in __init__).
    #       Begin listening for incoming connections and register the socket with your selector
    # HINT: Server sockets are read from, but never written to. This is important when registering the socket
    #       with your selector
    # HINT: Later on, you will need to differentiate between the server socket (which accepts new connections)
    #       and all other sockets that are passing messages back and forth between hosts. You will need someway
    #       to distinguish the server socket from all other sockets in order to know what to do when the socket
    #       is returned when you call self.sel.select()
    def setup_server_socket(self):
        self.print_info("Configuring the server socket...")
        self.my_sock = socket(AF_INET, SOCK_STREAM)
        self.my_sock.bind((self.connect_to_host_addr, self.port))
        self.my_sock.listen()
        self.my_sock.setblocking(False)

        events = selectors.EVENT_READ
        self.sel.register(self.my_sock, events, data=None)
        # TODO: Implement the above functionality
        


    # This function is responsible for connecting to a remote IRC server upon starting this server.
    # You should connect to the server at (self.connect_to_host_addr, self.connect_to_port)
    # TODO: Establish a connection with the remote server, register the new socket with your selector,
    #       and send a ServerRegistrationMessage to the server once you are connected. In this protocol, 
    #       all initial registration messages should have their last_hop_id set to 0. ***THIS IS VERY IMPORTANT***
    #       Future repetitions of this message should contain the ID of the server that repeated the message 
    #       in the last_hop_id field.
    # HINT: Remember that you can't call send() outside of the select() loop once the socket is 
    #       set to nonblocking.
    # HINT: This socket will need to be both read from and written to
    def connect_to_server(self):
        self.print_info("Connecting to remote server %s:%i..." % (self.connect_to_host, self.connect_to_port))
        self.client_sock = socket(AF_INET, SOCK_STREAM)
        self.client_sock.connect((self.connect_to_host_addr, self.connect_to_port))
        self.client_sock.setblocking(False)
        
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        my_sock_data = ConnectionData()
        

        self.sel.register(self.client_sock, events, my_sock_data)
        my_sock_data.write_buffer = ServerRegistrationMessage.bytes(self.id, 0, self.server_name, self.server_info)
        # TODO: Implement the above functionality
          


    # This is the main loop responsible for processing input and output on all sockets this server
    # is connected to. You should manage these connections using the selector you have instantiated.
    # TODO: Inside of the while not self.request_terminate loop, get a list of all sockets ready for processing
    #       from your selector, and then process these events. If the socket being processed is the server socket,
    #       call self.accept_new_connection(io_device). Otherwise, call self.handle_io_device_events(io_device, event_mask).
    #       Once the while loop has terminated (i.e. the program is shutting down), call self.cleanup()
    # HINT: Pass a short timeout value into your select() call (e.g. 0.1 seconds) to prevent your code from hanging
    #       when it is time to terminate it
    def check_IO_devices_for_messages(self):
        self.print_info("Listening for new connections on port " + str(self.port))
        # All calls to select() MUST be inside of this loop. Select is a blocking call, and we need to terminate the 
        # server in order to test its functionality. We will accomplish this by calling select() inside of a loop that
        # we can terminate by setting self.request_terminate to True.
        while not self.request_terminate:
            # TODO: Implement the above functionality
            if len(self.sel._fd_to_key) > 0:
                ready_IO = self.sel.select(timeout = 1)                     # Get a list of the ready IO devices
                for io_device , event_mask in ready_IO :
                    if io_device.data is None:                                # New socket to accept
                        self.accept_new_connection(io_device)
                    else:
                        self.handle_io_device_events(io_device, event_mask)
            
        self.cleanup()   



    # On shutting down the server, we need to release allocated resources associated with the server socket, with all
    # other sockets we've opened, and with our selector. Use this function to accomplish this
    # TODO: Perform any cleanup required upon termination of the program. This includes cleaning up both your sockets 
    #       and your selector
    # HINT: You'll need a list of all connected sockets in order to shut them down and unregister them here. You can get
    #       a list of the connected sockets by accessing a hidden dictionart of the selector: _fd_to_keys. You can extract
    #       a list of io_devices from this using the command: list(self.sel._fd_to_key.values())
    def cleanup(self):
        # TODO: Implement the above functionality
        self.sel.close()
        self.my_sock.close()



    # This function is responsible for handling new connection requests from other servers and from clients.
    # NOTE: At this point we don't yet know if the host who initiated this connection is a server or a client
    #       We won't find this out until we receive either a ServerRegistration or ClientRegistration message.
    # TODO: Accept the connection request and register it with your selector. You should configure all sockets
    #       for both READ and WRITE events. You will also need to create an instance of ConnectionData() and assign it
    #       to the data field when registering the connection. ConnectionData is a class created for this assignment.
    #       See the comments at the top of this file for more details. ConnectionData holds the write buffer
    #       associated with this socket
    def accept_new_connection(self, select_key):
        # TODO: Implement the above functionality
        conn, addr = select_key.fileobj.accept()
        conn.setblocking(False)

        data = ConnectionData()
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.sel.register(conn, events, data=data)



    # This function is responsible for handling events for a given IO device. This includes both
    # reading from the IO device and writing to the IO device.
    # TODO: Check to see if this is a READ event and/or a WRITE event (it is possible for it to be both).
    #       If it is a read event, read the bytes from the connection and process it. If you call recv but
    #       don't receive any bytes, this means that the client/server has closed their connection from
    #       the other side. In this case, you should unregister and close the socket.
    #       On receiving data, call self.handle_messages and pass in the received bytes
    #       If it is a write event, check the write_buffer for this socket to see if you have any bytes 
    #       that need to be written. You don't want to write empty data to your socket. Make sure you clear
    #       the write buffer once you've written it to the socket, as we don't want to send duplicate messages
    def handle_io_device_events(self, io_device, event_mask):
        # TODO: Implement the above functionality
        sock = io_device.fileobj
        if event_mask & selectors.EVENT_READ:
            recv_data = sock.recv(2048)  # Should be ready to read
            if recv_data:
                self.handle_messages(io_device, recv_data)
            else:
                self.sel.unregister(sock)
                sock.close()
        if event_mask & selectors.EVENT_WRITE:
            if io_device.data.write_buffer:
                sock.send(io_device.data.write_buffer)                 # Should be ready to write
                io_device.data.write_buffer = b""


    # This function parses the bytes in order to extract the messages contained therein and then
    # passes the messages to the appropriate message handler.
    # DO NOT MODIFY THIS FUNCTION
    def handle_messages(self, select_key, recv_data):
        messages = MessageParser.parse_messages(recv_data)

        for message in messages:
             # If we recognize the command, then process it using the assigned message handler
            if message.message_type in self.message_handlers:
                self.print_info("Received message from Host ID #%s \"%s\"" % (message.source_id, message.bytes))
                self.message_handlers[message.message_type](select_key, message)
            else:
                raise Exception("Unrecognized command: " + message)




    ###############################################################################################################
    ###############################################################################################################
    ## This next block contains several helper functions that will make it easier for you to send messages
    ## through the network. I recommend roughing out your ServerMessageHandler first to get a basic idea of the
    ## logic of that function, and then coming back to implement these
    ##

    # TODO: Using the provided information, store the provided message in the write_buffer for the associated socket
    def send_message_to_host(self, destination_id, message):
        if destination_id in self.hosts_db:
            self.print_info("Sending message to Host ID #%s \"%s\"" % (destination_id, message))
            # TODO: Implement the above functionality
            self.hosts_db[destination_id].write_buffer += message


    # When responding to a registration error, you will not yet know the ID of the host on the other side 
    # of the connection. In this case, you cannot reference self.hosts_db to access the write_buffer for this 
    # socket, but instead must access it directly through the io_device passed in to the registration handler.
    # You should only call this function when you need to send a response to a host in the event of an 
    # unsuccessful registration
    # TODO: Using the provided information, store the provided message in the write_buffer for the associated socket
    def send_message_to_unknown_io_device(self, io_device, message):
        self.print_info("Sending message to an unknown IO device \"%s\"" % (message))
        # TODO: Implement the above functionality
        io_device.data.write_buffer += message


    # Messages will sometimes need to be sent to every server in the network. This is a helper function
    # to make that process easier. You may call send_message_to_host() in this function. Remember that, when broadcasting,
    # you should only try and send the message to servers that are directly adjacent to you. These servers will then
    # pass the message to server adjacent to them, continuing the broadcast. 
    # You will sometimes want to exclude a host from the broadcast (e.g. you don't want to broadcast a registration
    # message back to the host that sent it to you originally). You can use the ignore_host_id property
    # to help with this.  When broadcasting, check to make sure that a hosts ID is not equal to the value of
    # ignore_host_id prior to sending prior to sending the message.
    # TODO: Write the code required to broadcast the message to adjacent servers, except for a server included in the
    #       ignore_host_id parameter
    def broadcast_message_to_servers(self, message, ignore_host_id=None):
        # TODO: Implement the above functionality
        for server_id in self.adjacent_server_ids:
            if server_id != ignore_host_id:
                # self.print_info("////////////////////////// {} : {}".format(server_id, self.adjacent_server_ids))
                self.send_message_to_host(server_id, message)


    # This function performs the same function as the broadcast_message_to_servers function, except it broadcasts
    # the message to adjacent clients. These functions are separated from each other as you will sometimes need to send
    # a message to either servers or clients, not both. If you need to send to both, simply call both functions.
    # TODO: Write the code required to broadcast the message to adjacent clients, except for a server included in the
    #       ignore_host_id parameter
    def broadcast_message_to_adjacent_clients(self, message, ignore_host_id=None):
        # TODO: Implement the above functionality
        for client_id in self.adjacent_user_ids:
            if client_id != ignore_host_id:
                self.send_message_to_host(client_id, message)




    ###############################################################################################################
    ###############################################################################################################
    ## You will need to complete this next function to pass the three Server test cases
    ##

    ######################################################################
    # Server Registration Message handler
    # This function handles the initial registrion process for new servers. Upon receiving a Server Registration message,
    # check to ensure that this ID does not yet exist in the network. If the ID does already exist, send a StatusUpdateMessage
    # with message code 0x02 and the message content "A machine has already registered with ID [X]", where [X] is replaced with 
    # the ID in the registration message, and then return from the function.. Since you don't know the ID of the new server, 
    # use a destination_ID of 0 when making this StatusUpdateMessage.
    # 
    # If the ID is unique, you should create a new ServerData object with the new server's information and register it in 
    # self.hosts_db. You will need to determine what the first_link_id value should be when creating the ServerData object. 
    #
    # You should also determine if the new server is adjacent to this server. If so, add its ID to self.adjacent_server_ids 
    # and modify the provided io_device to replace the associated data object with your new ServerData object. You can do this 
    # by calling:
    #    self.sel.modify(io_device.fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE, my_new_server_data_obj)
    #
    # If this registration message was sent from a brand new server, this server should inform it of all other connected
    # servers and clients on the network. You can accomplish this by sending it ServerRegistrationMessages and 
    # ClientRegistrationMessages containing the details of each Server and Client on the network. These messages will then be 
    # handled by the new server's respective ServerRegistration and ClientRegistration message handlers. You can check if a 
    # given host in self.hosts_db is a Server or a Client using python's isinstance() command.
    #  
    # Finally, broadcast a message informing the rest of the network about this new server.
    def handle_server_registration_message(self, io_device, message):
        # TODO: Implement the above functionality
        new_server_id = message.source_id
        new_last_hop_id = message.last_hop_id
        new_server_name = message.server_name
        new_server_info = message.server_info
        new_server = ServerData(new_server_id, new_server_name, new_server_info)

        if new_last_hop_id == 0:
            # add friends and host db
            self.hosts_db[new_server_id] = new_server
            self.adjacent_server_ids.append(new_server_id)
            self.sel.modify(io_device.fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE, new_server)
            new_server.first_link_id = new_server_id

            # Send "It's me"
            message = ServerRegistrationMessage.bytes(self.id, self.id, self.server_name, self.server_info)
            self.send_message_to_host(new_server_id, message)

            # tell "There are also another hosts"
            for servers in self.hosts_db:
                host = self.hosts_db[servers]
                
                if isinstance(host, ServerData):
                    # send to server
                    if servers != new_server_id:
                        message = ServerRegistrationMessage.bytes(self.id, host.id, host.server_name, host.server_info)
                        self.send_message_to_host(new_server_id, message)
                    pass
                else:
                    # # send to client
                    if servers != new_server_id:
                        message = ClientRegistrationMessage.bytes(self.id, host.id, host.client_name, host.client_info)
                        self.send_message_to_host(new_server_id, message)
                    pass
            pass
        else:
            if new_last_hop_id == new_server_id:
                if new_server_id not in self.hosts_db:
                    # add friends and host db
                    self.hosts_db[new_server_id] = new_server
                    if new_server_id not in self.adjacent_server_ids:
                        self.adjacent_server_ids.append(new_server_id)
                        self.sel.modify(io_device.fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE, new_server)
                        new_server.first_link_id = new_server_id
                pass
            else:
                new_server = ServerData(new_last_hop_id, new_server_name, new_server_info)
                if new_last_hop_id not in self.hosts_db:
                    # add friends and host db
                    self.hosts_db[new_last_hop_id] = new_server
                pass

        message = ServerRegistrationMessage.bytes(self.id, new_server.id, new_server_name, new_server_info)
        self.broadcast_message_to_servers(message, new_server_id)




    ###############################################################################################################
    ###############################################################################################################
    ## You will need to complete this next function to pass the four Server-Client test cases
    ##

    ######################################################################
    # Client Registration Message handler
    # This function handles the initial registrion process for new client. Upon receiving a Client Registration message,
    # check to ensure that this ID does not yet exist in the network. If the ID does already exist, send a StatusUpdateMessage
    # with message code 0x02 and the message content "A machine has already registered with ID [X]", where [X] is replaced with 
    # the ID in the registration message, and then return from the function. Since you don't know the ID of the new client, 
    # use a destination_ID of 0 when making this StatusUpdateMessage.
    # 
    # If the ID is unique, you should create a new ClientData object with the new client's information and register it in 
    # self.hosts_db. You will need to determine what the first_link_id value should be when creating the ClientData object. 
    #
    # You should also determine if the new client is adjacent to this server. If so, add its ID to self.adjacent_client_ids 
    # and modify the provided io_device to replace the associated data object with your new ClientData object. You can do this 
    # by calling:
    #    self.sel.modify(io_device.fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE, my_new_client_data_obj)
    # You should also send a Welcome status update to the newly connected adjacent client. The message code should be 0x00 and
    # the message content should be "Welcome to the Clemson Relay Chat network [X]", where [X] is the client's name.
    #
    # If this registration message was sent from a brand new client, this server should inform it of all other connected
    # clients on the network. You can accomplish this by sending it ClientRegistrationMessages containing the details of 
    # each other Client on the network. These messages will then be handled by the new client's respective ClientRegistration
    # message handlers. You can check if a given host in self.hosts_db is a Client using python's isinstance() command.
    #  
    # Finally, broadcast a message informing the rest of the network about this new client.
    def handle_client_registration_message(self, select_key, message):
        # TODO: Implement the above functionality
        new_client_id = message.source_id
        new_last_hop_id = message.last_hop_id
        new_client_name = message.client_name
        new_client_info = message.client_info
        new_client = ClientData(new_client_id, new_client_name, new_client_info)

        if new_last_hop_id == 0:
            # add friends and host db
            self.hosts_db[new_client_id] = new_client
            self.adjacent_user_ids.append(new_client_id)
            self.sel.modify(select_key.fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE, new_client)
            new_client.first_link_id = new_client_id

            
            # tell "There are also another hosts"
            for current_host in self.hosts_db:
                host = self.hosts_db[current_host]
                # check the instance of hosts_db
                if isinstance(host, ServerData):
                    # send to server
                    pass
                else:
                    # send to client
                    if current_host != new_client_id:
                        message = ClientRegistrationMessage.bytes(host.id, host.id, host.client_name, host.client_info)
                        self.send_message_to_host(new_client_id, message)
                    pass
                

        message = ClientRegistrationMessage.bytes(new_client_id, new_client.id, new_client_name, new_client_info)
        self.broadcast_message_to_adjacent_clients(message, new_client_id)




    ###############################################################################################################
    ###############################################################################################################
    ## You will need to complete this next function to pass some of the four Status Update test cases
    ##

    ######################################################################
    # Status Message handler
    # Upon receiving a status message, check to see if the destination id is your ID, or if it is 0. If either of 
    # these are true, append the content of the message to self.status_updates.log.
    # Otherwise, if the destination_id of the StatusUpdateMessage exists, send it on to the intended destination.
    # This should be a very short function
    def handle_status_message(self, select_key, message):
        # TODO: Implement the above functionality
        new_client_id = message.source_id
        new_last_hop_id = message.last_hop_id
        new_client_name = message.client_name
        new_client_info = message.client_info
        new_client = ClientData(new_client_id, new_client_name, new_client_info)

        if new_last_hop_id == 0:
            # add friends and host db
            self.hosts_db[new_client_id] = new_client
            self.adjacent_user_ids.append(new_client_id)
            self.sel.modify(select_key.fileobj, selectors.EVENT_READ | selectors.EVENT_WRITE, new_client)
            new_client.first_link_id = new_client_id

            
            # tell "There are also another hosts"
            for current_host in self.hosts_db:
                host = self.hosts_db[current_host]
                # check the instance of hosts_db
                if isinstance(host, ServerData):
                    # send to server
                    pass
                else:
                    # send to client
                    if current_host != new_client_id:
                        message = ClientRegistrationMessage.bytes(host.id, host.id, host.client_name, host.client_info)
                        self.send_message_to_host(new_client_id, message)
                    pass
                

        message = ClientRegistrationMessage.bytes(new_client_id, new_client.id, new_client_name, new_client_info)
        self.broadcast_message_to_adjacent_clients(message, new_client_id)




    ###############################################################################################################
    ###############################################################################################################
    ## You will need to complete this next function to pass some of the four Chat Message test cases
    ##

    ######################################################################
    # Client Chat Message handler
    # Upon receiving a chat message, check to see if the intended destintion_id exists. If so, forward the chat on to
    # the intended destination. 
    # If the destination id does not exist, send a StatusUpdateMessage with an UnknownID message code of 0x01 with the 
    # message content "Unknown ID [X]", where [X] is replaced with the Unknown ID
    def handle_client_chat_message(self, select_key, message):
        # TODO: Implement the above functionality
        pass



    ###############################################################################################################
    ###############################################################################################################
    ## You will need to complete this next function to pass the Client Quit Message test cases
    ##

    ######################################################################
    # Client Quit Message handler
    # This function handles the when clients quit the network. Upon receiving a Client Quit message, check to make sure that
    # this user exists in your hosts_db dictionary. If so, broadcast a message to all other servers and clients that this 
    # client is quitting. Make sure you don't broadcast the message back to the client that is quitting.
    # 
    # You should then remove the client from your hosts_db dictionary and, if it is adjacent to this server, from the 
    # adjacent_users_id list.
    def handle_client_quit_message(self, io_device, message):
        # TODO: Implement the above functionality
        new_client_id = message.source_id
        new_last_hop_id = message.last_hop_id
        new_client_name = message.client_name
        new_client_info = message.client_info
        new_client = ClientData(new_client_id, new_client_name, new_client_info)

        if new_last_hop_id == 0:
            # add friends and host db
            self.hosts_db[new_client_id] = new_client
            self.adjacent_user_ids.append(new_client_id)
            new_client.first_link_id = new_client_id

            
            # tell "There are also another hosts"
            for current_host in self.hosts_db:
                host = self.hosts_db[current_host]
                # check the instance of hosts_db
                if isinstance(host, ServerData):
                    # send to server
                    pass
                else:
                    # send to client
                    if current_host != new_client_id:
                        message = ClientRegistrationMessage.bytes(host.id, host.id, host.client_name, host.client_info)
                        self.send_message_to_host(new_client_id, message)
                    pass
                

        message = ClientRegistrationMessage.bytes(new_client_id, new_client.id, new_client_name, new_client_info)
        self.broadcast_message_to_adjacent_clients(message, new_client_id)
    
    

    # DO NOT EDIT ANY OF THE FUNCTIONS BELOW THIS LINE
    # These are helper functions to assist with logging and list management
    # ----------------------------------------------------------------------


    ######################################################################
    # This block of functions enables logging of info, debug, and error messages
    # Do not edit these functions. init_logging() is already called by the template code
    # You are encouraged to use print_info, print_debug, and print_error to log
    # messages useful to you in development

    def init_logging(self):
        # If we don't include a log file name, then don't log
        if not self.log_file:
            return

        # Get a reference to the logger for this program
        self.logger = logging.getLogger("IRCServer")
        __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

        # Create a file handler to store the log files
        fh = logging.FileHandler(os.path.join(__location__, 'Logs', '%s' % self.log_file), mode='w')

        # Set up the logging level. It defaults to INFO
        log_level = logging.INFO
        
        # Define a formatter that will be used to format each line in the log
        formatter = logging.Formatter(
            ("%(asctime)s - %(name)s[%(process)d] - "
             "%(levelname)s - %(message)s"))

        # Assign all of the necessary parameters
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        self.logger.setLevel(log_level)
        self.logger.addHandler(fh)

    def print_info(self, msg):
        print("[%s] \t%s" % (self.server_name,msg))
        if self.logger:
            self.logger.info(msg)



    # This function takes two lists and returns the union of the lists. If an object appears in both lists,
    # it will only be in the returned union once.
    def union(self, lst1, lst2): 
        final_list = list(set(lst1) | set(lst2)) 
        return final_list

    # This function takes two lists and returns the intersection of the lists.
    def intersect(self, lst1, lst2): 
        final_list = list(set(lst1) & set(lst2)) 
        return final_list

    # This function takes two lists and returns the objects that are present in list1 but are NOT
    # present in list2. This function is NOT commutative
    def diff(self, list1, list2):
        return (list(set(list1) - set(list2)))