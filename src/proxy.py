import sys, os, time, socket, select

class ProxyServer:
    def __init__(self, host: str = 'localhost', port: int = 8888):
        self.host = host
        self.port = port

        self.inputs: list[socket.socket] = []      # All sockets to read from
        self.outputs: list[socket.socket] = []     # Sockets ready to write to
        self.message_queues: dict[socket.socket, bytes] = {}  # client_socket -> data to send

        self.client_to_server: dict[socket.socket, socket.socket] = {}  # client_socket -> server_socket
        self.server_to_client: dict[socket.socket, socket.socket] = {}  # server_socket -> client_socket
        self.request_buffers: dict[socket.socket, bytes] = {}   # client_socket -> accumulated request
        self.response_buffers: dict[socket.socket, bytes] = {}  # client_socket -> data from server 

        self.listener: socket.socket = self.create_listening_socket()
        self.inputs.append(self.listener)

    def create_listening_socket(self) -> socket.socket:
        sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen()
        sock.setblocking(False)
        return sock

    def run(self) -> None:
        while True:
            readable, writable, _ = select.select(self.inputs, self.outputs, [])

            for sock in readable:
                if sock is self.listener:
                    self.accept_new_client()
                elif sock in self.client_to_server:
                    self.receive_from_server(sock)
                elif sock in self.inputs:
                    self.receive_from_client(sock)

            for sock in writable:
                if sock in self.response_buffers:
                    self.send_to_client(sock)

    def accept_new_client(self) -> None:
        client_socket, _ = self.listener.accept()
        client_socket.setblocking(False)
        self.inputs.append(client_socket)
        self.request_buffers[client_socket] = b""

    def receive_from_client(self, client_socket: socket.socket) -> None:
        try:
            data = client_socket.recv(4096)
        except ConnectionResetError:
            data = b""

        if data:
            self.request_buffers[client_socket] += data
            if b"\r\n\r\n" in self.request_buffers[client_socket]:
                self.forward_request_to_server(client_socket)
        else:
            self.cleanup(client_socket)

    def forward_request_to_server(self, client_socket: socket.socket) -> None:
        request_data = self.request_buffers[client_socket]
        server_host = self.extract_host(request_data)
        if not server_host:
            self.cleanup(client_socket)
            return

        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setblocking(False)
            server_socket.connect_ex((server_host, 80))
        except Exception:
            self.cleanup(client_socket)
            return

        self.inputs.append(server_socket)
        self.client_to_server[client_socket] = server_socket
        self.server_to_client[server_socket] = client_socket

        try:
            server_socket.sendall(self.adjust_request(request_data))
        except BlockingIOError:
            pass  # It'll send when writable in a future iteration

        self.response_buffers[client_socket] = b""

    def receive_from_server(self, server_socket: socket.socket) -> None:
        client_socket = self.server_to_client[server_socket]
        try:
            data = server_socket.recv(4096)
        except ConnectionResetError:
            data = b""

        if data:
            self.response_buffers[client_socket] += data
            if client_socket not in self.outputs:
                self.outputs.append(client_socket)
        else:
            self.cleanup(server_socket)

    def send_to_client(self, client_socket: socket.socket) -> None:
        buffer = self.response_buffers[client_socket]
        if buffer:
            try:
                sent = client_socket.send(buffer)
                self.response_buffers[client_socket] = buffer[sent:]
            except BlockingIOError:
                return

        if not self.response_buffers[client_socket]:
            self.outputs.remove(client_socket)
            self.cleanup(client_socket)

    def cleanup(self, sock: socket.socket) -> None:
        # Remove from all mappings and close
        if sock in self.inputs:
            self.inputs.remove(sock)
        if sock in self.outputs:
            self.outputs.remove(sock)
        sock.close()

        if sock in self.client_to_server:
            server = self.client_to_server.pop(sock)
            self.server_to_client.pop(server, None)
            self.cleanup(server)

        if sock in self.server_to_client:
            client = self.server_to_client.pop(sock)
            self.client_to_server.pop(client, None)
            self.cleanup(client)

        self.request_buffers.pop(sock, None)
        self.response_buffers.pop(sock, None)

    def extract_host(self, request_data: bytes) -> str | None:
        try:
            lines: list[str] = request_data.decode().split('\r\n')
            for line in lines:
                if line.lower().startswith('host:'):
                    return line.split(':', 1)[1].strip()
        except Exception:
            return None
        return None

    def adjust_request(self, request_data: bytes) -> bytes:
        lines = request_data.decode().split('\r\n')
        new_lines = []
        for line in lines:
            if line.lower().startswith('proxy-connection:'):
                continue
            elif line.lower().startswith('connection:'):
                new_lines.append('Connection: close')
            else:
                new_lines.append(line)
        return '\r\n'.join(new_lines).encode()


if __name__ == '__main__':
    timeout: int = int(sys.argv[1]) if len(sys.argv) > 1 else 120  # not used yet (for step 4)
    proxy: ProxyServer = ProxyServer()
    proxy.run()
