import sys, os, time, socket, select

class ProxyServer:
    def __init__(self, host: str = 'localhost', port: int = 8888):
        print(f"Initializing ProxyServer on {host}:{port}")
        self.host = host
        self.port = port

        self.inputs: list[socket.socket] = []      # All sockets to read from
        self.outputs: list[socket.socket] = []     # Sockets ready to write to
        self.message_queues: dict[socket.socket, bytes] = {}  # client_socket -> data to send

        self.client_to_server: dict[socket.socket, socket.socket] = {}  # client_socket -> server_socket
        self.server_to_client: dict[socket.socket, socket.socket] = {}  # server_socket -> client_socket
        self.request_buffers: dict[socket.socket, bytes] = {}   # client_socket -> accumulated request
        self.response_buffers: dict[socket.socket, bytes] = {}  # client_socket -> data from server 
        self.server_done: dict[socket.socket, bool] = {}  # client_socket -> True/False


        self.listener: socket.socket = self.create_listening_socket()
        self.inputs.append(self.listener)
        print("ProxyServer initialization complete")

    def create_listening_socket(self) -> socket.socket:
        print(f"Creating listening socket on {self.host}:{self.port}")
        sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen()
        sock.setblocking(False)
        print("Listening socket created successfully")
        return sock

    def run(self) -> None:
        print("Starting proxy server main loop")
        while True:
            readable, writable, _ = select.select(self.inputs, self.outputs, [])
            self.handle_readables(readable)
            self.handle_writables(writable)
        
    def handle_readables(self, readable):
        for sock in readable:
            if sock is self.listener:
                self.accept_new_client()
            elif sock in self.server_to_client:
                self.receive_from_server(sock)
            elif sock in self.inputs:
                self.receive_from_client(sock)

    def handle_writables(self, writable):
        for sock in writable:
            if sock in self.response_buffers:
                self.send_to_client(sock)
            elif sock in self.message_queues:
                self.send_to_server(sock)

    def send_to_server(self, server_socket: socket.socket) -> None:
        try:
            data = self.message_queues[server_socket]
            sent = server_socket.send(data)
            print(f"Sent {sent} bytes to server")
            if sent < len(data):
                self.message_queues[server_socket] = data[sent:]
            else:
                del self.message_queues[server_socket]
                if server_socket in self.outputs:
                    self.outputs.remove(server_socket)
                if server_socket not in self.inputs:
                    self.inputs.append(server_socket)
                print("All data sent to server, now listening for response")
        except Exception as e:
            print(f"Error sending data to server: {e}")
            self.cleanup(server_socket)



    def accept_new_client(self) -> None:
        client_socket, client_address = self.listener.accept()
        
        print(f"New client connected from {client_address}")
        client_socket.setblocking(False)
        
        self.inputs.append(client_socket)
        self.request_buffers[client_socket] = b""
        
        print(f"Client {client_address} added to inputs list")

    def receive_from_client(self, client_socket: socket.socket) -> None:
        # if client_socket not in self.request_buffers:
        #     # If we've already processed and cleaned up this client, ignore further reads
        #     print(f"Ignoring extra data from closed client socket: {client_socket}")
        #     return
        try:
            data = client_socket.recv(4096)
            print(f"Received {len(data)} bytes from client")
        except ConnectionResetError:
            print("Connection reset by client")
            data = b""

        if data:
            # Check if the client socket is in the request_buffers dictionary
            if client_socket not in self.request_buffers:
                print(f"Client socket not found in request_buffers, adding it")
                self.request_buffers[client_socket] = b""
                
            self.request_buffers[client_socket] += data
            print(f"Accumulated {len(self.request_buffers[client_socket])} bytes in request buffer")
            if b"\r\n\r\n" in self.request_buffers[client_socket]:
                print("Complete request received, forwarding to server")
                self.forward_request_to_server(client_socket)
        else:
            #TODO: We are closing the socket here, maybe an issue?
            print("No data received from client, cleaning up")
            self.cleanup(client_socket)

    def forward_request_to_server(self, client_socket: socket.socket) -> None:
        
        # Get the request data from the request_buffers dict
        request_data = self.request_buffers[client_socket]

        # Only decode the header part (up to \r\n\r\n)
        header_end = request_data.find(b"\r\n\r\n")
        
        # Printing the header, with error handling
        try:
            header_str = request_data[:header_end].decode(errors='replace')
        except Exception as e:
            print("Error decoding header:", e)
            header_str = "<undecodable header>"
        
        print(f"Forwarding request to server:\n{header_str}\n")

        # Extract the host from the request
        server_host = self.extract_host(request_data)
        
        if not server_host:
            print("Could not extract host from request, cleaning up")
            self.cleanup(client_socket)
            return
        
        # if server_host == "favicon.ico":
        #     print("Favicon request, skipping")
        #     return  

        # Connect to the server
        print(f"Connecting to server: {server_host}")
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setblocking(False)
            error_code = server_socket.connect_ex((server_host, 80))

            # Adjust the request to the server's format
            adjusted = self.adjust_request(request_data)
            print("Adjusted request (first 300 bytes or so):")
            print(adjusted[:300].decode(errors='replace'))

            # Add the adjusted request to the message_queues dict
            
            self.message_queues[server_socket] = adjusted
            
            
            # Add the server socket to the outputs list
            self.outputs.append(server_socket) 

        
            print(f"Connection to {server_host} initiated, waiting for completion")
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            self.cleanup(client_socket)
            return

        # Add the server socket to the inputs list
        # self.inputs.append(server_socket) <- NOT GOOD.

        # Add the server socket to the client_to_server and server_to_client mappings
        self.client_to_server[client_socket] = server_socket
        self.server_to_client[server_socket] = client_socket

        # Initialize the response buffer for the client
        self.response_buffers[client_socket] = b"" #TODO: this might be too early?
        print("Response buffer initialized for client")

    def receive_from_server(self, server_socket: socket.socket) -> None:
        client_socket = self.server_to_client.get(server_socket)
        # if client_socket is None:
        #     print("Client socket not found for this server")
        #     self.cleanup(server_socket)
        #     return

        #TODO: is the the best way to handle this?
        try:
            data: bytes = server_socket.recv(4096)
            print(f"Received {len(data)} bytes from server")
        except ConnectionResetError:
            print("Connection reset by server")
            data = b""

        if data:
            self.response_buffers[client_socket] += data
            print(f"Accumulated {len(self.response_buffers[client_socket])} bytes in response buffer")
            if client_socket not in self.outputs:
                self.outputs.append(client_socket)
                print("Added client to outputs list")
        else:
            # No more data from server
            print("No more data from server, marking as done")
            self.inputs.remove(server_socket)
            server_socket.close()
            self.server_done[client_socket] = True


    def send_to_client(self, client_socket):
        buffer = self.response_buffers[client_socket]
        if buffer:
            try:
                sent = client_socket.send(buffer)
                print(f"Sent {sent} bytes to client")
                self.response_buffers[client_socket] = buffer[sent:]
                print(f"Remaining in buffer: {len(self.response_buffers[client_socket])} bytes")
            except BlockingIOError:
                print("Client socket not ready for writing, will retry later")
                return

        # Only clean up if server is done AND buffer is empty
        if self.server_done.get(client_socket, False) and not self.response_buffers[client_socket]:
            print("Server done and buffer empty, cleaning up client")
            if client_socket in self.outputs:
                self.outputs.remove(client_socket)
            self.cleanup(client_socket)


    def cleanup(self, sock: socket.socket) -> None:
        print(f"Cleaning up socket {sock}")
        # Remove from all mappings and close
        if sock in self.inputs:
            self.inputs.remove(sock)
            print("Removed from inputs list")
        if sock in self.outputs:
            self.outputs.remove(sock)
            print("Removed from outputs list")
        sock.close()
        print("Socket closed")

        if sock in self.client_to_server:
            server = self.client_to_server.pop(sock)
            print("Removed client-to-server mapping")
            self.server_to_client.pop(server, None)
            print("Removed server-to-client mapping")
            self.cleanup(server)

        if sock in self.server_to_client:
            client = self.server_to_client.pop(sock)
            print("Removed server-to-client mapping")
            self.client_to_server.pop(client, None)
            print("Removed client-to-server mapping")
            self.cleanup(client)

        self.request_buffers.pop(sock, None)
        self.response_buffers.pop(sock, None)
        self.server_done.pop(sock, None)
        print("Cleaned up all mappings for socket")


    def extract_host(self, request_data: bytes) -> str | None:
        try:
            first_line = request_data.decode().split('\r\n')[0]
            parts = first_line.split()
            if len(parts) < 2:
                print("Invalid request format: not enough parts")
                return None
                
            full_path = parts[1]  # e.g., /www.cs.toronto.edu/~ylzhang/
            if full_path.startswith("/"):
                full_path = full_path[1:]  # strip the leading slash
                
            # Extract just the host part (first component before the first slash)
            host_parts = full_path.split("/")
            host = host_parts[0]
            
            # Validate that this is actually a host (should contain at least one dot)
            if "." not in host:
                print(f"Not a valid host: {host}")
                return None
                
            print(f"Extracted host from path: {host}")
            
            return host
        except Exception as e:
            print(f"Error extracting host: {e}")
            return None

    def adjust_request(self, request_data: bytes) -> bytes:
        lines = request_data.decode(errors='replace').split('\r\n')

        # Step 1: Rewrite the request line (GET /path HTTP/1.1)
        lines[0], host = self.rewrite_request_line(lines[0])

        # Step 2: Rewrite or insert the Host header
        lines = self.rewrite_host_header(lines, host)

        # Step 3: Clean up connection headers
        lines = self.rewrite_connection_headers(lines)

        return '\r\n'.join(lines).encode()

    def rewrite_request_line(self, request_line: str) -> tuple[str, str]:
        parts = request_line.split()
        if len(parts) < 2:
            return request_line, ""

        full_path = parts[1].lstrip('/')
        path_parts = full_path.split('/', 1)

        if len(path_parts) == 2:
            host, path = path_parts
            if not path:
                path = "/"
            new_line = f"{parts[0]} /{path} {parts[2]}"
            return new_line, host

        elif len(path_parts) == 1:
            host = path_parts[0]
            new_line = f"{parts[0]} / {parts[2]}"
            return new_line, host

        return request_line, ""

    def rewrite_host_header(self, lines: list[str], host: str) -> list[str]:
        lines = [line for line in lines if not line.lower().startswith('host:')]
        if host:
            lines.insert(1, f"Host: {host}")
        return lines

    def rewrite_connection_headers(self, lines: list[str]) -> list[str]:
        new_lines = []
        for line in lines:
            if line.lower().startswith("proxy-connection:"):
                continue
            elif line.lower().startswith("connection:"):
                new_lines.append("Connection: close")
            else:
                new_lines.append(line)
        return new_lines


if __name__ == '__main__':
    timeout: int = int(sys.argv[1]) if len(sys.argv) > 1 else 120  # not used yet (for step 4)
    print(f"Starting proxy server with timeout: {timeout} seconds")
    hostname = socket.gethostname()
    print(f"Hostname: {hostname}")
    proxy: ProxyServer = ProxyServer(host=hostname, port=8888)
    proxy.run()
