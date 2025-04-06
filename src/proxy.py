import sys
import os
import time
import socket
import select

# Constants
LISTEN_PORT = 8888
BUFFER_SIZE = 4096



"""
    Parses an HTTP request to extract the target host and path.
    
    The function expects requests in the format:
    GET /www.example.com/path HTTP/1.1
    
    Args:
        request (str): The raw HTTP request string
"""
def parse_request(request:str) -> tuple[str, str]:
    try:
        lines = request.split('\r\n')
        first_line = lines[0]
        print("First request line:", first_line)

        method, raw_path, protocol = first_line.split()

        if not raw_path.startswith("/"):
            return None, None

        # The path starts with something like /www.example.org or /www.example.org/some/page
        stripped_path = raw_path.lstrip('/')  # remove the first slash

        parts = stripped_path.split('/', 1)
        host = parts[0]  # 'www.example.org'
        path = '/' + parts[1] if len(parts) > 1 else '/'

        return host, path
    except Exception as e:
        print("Failed to parse request:", e)
        return None, None



# handle client function
def handle_client(client_socket:socket) -> None:
    try:
        request:str = client_socket.recv(BUFFER_SIZE).decode()
    
    
        # calls parse_request function
        host, path = parse_request(request)
    

        if host is None:
            print("Invalid request, Host is None")
            client_socket.close()
            return

        # calls forward_request_to_server function
        print(f"Forwarding request to {host}{path}")
        response = forward_request_to_server(host, path, request)
        
        
        client_socket.sendall(response)
    except Exception as e:
        print("Error handling client:", e)
    finally:
        client_socket.close()
        
    

    


# forward request to server function
def forward_request_to_server(host:str, path:str, request:str) -> bytes:
    # creates a client socket
    # remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # remote.connect((host, 80))  # Connect to the server on port 80 (HTTP)
    # # sends the request to the server
    # try:
    
    pass
    # receives the response from the server
    
    # sends response back to the client




# main function
def main():

    # Create and configure the server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("localhost", LISTEN_PORT))
    server_socket.listen()

    print(f"Server listening on {"localhost"}:{LISTEN_PORT}")

    # List of sockets to monitor
    sockets_list = [server_socket]
    clients = {}

    while True:
        # Wait for any socket to be ready (readable)
        read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list)

        for notified_socket in read_sockets:
            if notified_socket == server_socket:
                # New connection
                client_socket, client_address = server_socket.accept()
                sockets_list.append(client_socket)
                clients[client_socket] = client_address
                print(f"New connection from {client_address}")
            else:
                # Data from an existing client
                try:
                    handle_client(notified_socket)
                    # data = notified_socket.recv(1024)
                    # if not data:
                    #     # Connection closed
                    #     print(f"Closed connection from {clients[notified_socket]}")
                    #     sockets_list.remove(notified_socket)
                    #     del clients[notified_socket]
                    #     notified_socket.close()
                    # else:
                    #     print(f"Received from {clients[notified_socket]}: {data.decode()}")
                    #     notified_socket.sendall(b"Message received!")
                except:
                    sockets_list.remove(notified_socket)
                    notified_socket.close()

        # Handle any exceptions
        for notified_socket in exception_sockets:
            sockets_list.remove(notified_socket)
            notified_socket.close()



if __name__ == "__main__":
    main()
