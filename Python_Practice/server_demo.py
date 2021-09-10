
from socket import *

INCOMING_HOSTS = ''
INCOMING_PORT = 3604

server_sock = socket(AF_INET, SOCK_STREAM)

server_sock.bind((INCOMING_HOSTS, INCOMING_PORT))

server_sock.listen(5)

new_sock, client_addr = server_sock.accept()

message = new_sock.recv()

