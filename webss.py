#-*-coding:utf-8-*-

import sys
import base64
import hashlib
import socket
import struct
from http import client
from socketserver import ThreadingTCPServer, StreamRequestHandler

guid = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

class BaseWSRequestHandler(StreamRequestHandler):
    def parse_request(self):
        """
        The handshake request parse
        When Connection header is Upgrade, stored sec_webscoket_key header
        Return True for success
        """
        self.sec_websocket_key = None
        self.close_connection = True

        self.headers = client.parse_headers(self.rfile)
        conntype = self.headers.get('Connection', "")
        if conntype.lower() == 'closing':
            self.close_connection = True

        elif conntype.lower() == 'upgrade':
            self.close_connection = False

            self.sec_websocket_key = self.headers.get('Sec-WebSocket-Key', "")

        return True

    def handle_accept(self):
        """
        Fixed guid to the value from sec_webscoekt_key header
        Applies the SHA-1 hashing function, and encodes the result using base64
        Return True for success
        """
        if hasattr(self, 'sec_websocket_key'):
            fixed_str = str.encode(self.sec_websocket_key+guid)
            sha1_key = hashlib.sha1(fixed_str).digest()
            base64_key = base64.b64encode(sha1_key)
            self.sec_websocket_accept = bytes.decode(base64_key)
            return True

    def handle_one_request(self):
        """
        Handle a single websocket request
        If the connection is established, you need to override the method
        and You can use self.do_Receive() method and self.do_Send() method
        to receive and send messages
        """
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                return
            try:
                self.handle_accept()
                self.send_response()
            except:
                self.close_connection = True
            method = getattr(self, 'method')
            method()
            self.wfile.flush()
        except socket.timeout:
            self.close_connection = True
            return

    def send_response(self):
        """Send response header to the headers buffer"""
        self._headers_buffer = []
        if hasattr(self, '_headers_buffer'):
            self._headers_buffer.append(b'HTTP/1.1 101 Switching Protocols\r\n')
        self.send_header('Upgrade','websocket')
        self.send_header('Connection', 'Upgrade')
        if hasattr(self, 'sec_websocket_accept'):
            self.send_header('Sec-WebSocket-Accept', self.sec_websocket_accept)

        self.end_headers()

    def handle(self):
        self.close_connection = True
        self.handle_one_request()
        while not self.close_connection:
            self.handle_one_request()

    def send_header(self, keyword, value):
        """Send the header to the headers buffer."""
        if not hasattr(self, '_headers_buffer'):
            self._headers_buffer = []
        self._headers_buffer.append(
                str.encode("%s: %s\r\n" % (keyword, value)))

    def end_headers(self):
        """Ending the heanders"""
        self._headers_buffer.append(b"\r\n")
        self.flush_headers()

    def flush_headers(self):
        if hasattr(self, '_headers_buffer'):
            self.wfile.write(b"".join(self._headers_buffer))
            self._headers_buffer = []

    def _frame_decode(self, frame, m, n):
        """Decode the frame from self.do_Receive() method"""
        list = []
        i = 0
        masks, data = frame[m:n], frame[n:]
        for c in data:
            list.append( c^masks[i%4] )
            i += 1
        return bytes(list).decode()

    def do_Receive(self):
        """Return the real message"""
        if self.close_connection == False:
            try:
                msg = self.request.recv(1024)
                msg_len = msg[1] & 127
                if msg_len == 126:
                    d = self._frame_decode(msg, 4, 8)
                elif msg_len == 127:
                    d = self._frame_decode(msg, 10, 14)
                else:
                    d = self._frame_decode(msg, 2, 6)
                return d
            except:
                self.rfile.close()
                self.close_connection = True


    def _pack(self, fmt, msg_encode_len, msg_encode, value):
        """Pack message from self.Send() method to be binary data"""
        r = [b'\x81']
        if value == None:
            pack = struct.pack(fmt, msg_encode_len)
        else:
            pack = struct.pack(fmt, value, msg_encode_len)
        r.append(pack)
        r.append(msg_encode)
        d = b''.join(r)
        return d

    def do_Send(self, msg):
        """Send the packed message"""
        if self.close_connection == False:
            try:
                msg_encode = str.encode(msg)
                msg_encode_len = msg_encode.__len__()
                if msg_encode_len < 126:
                    d = self._pack('B', msg_encode_len, msg_encode, None)
                elif msg_encode_len <= 0xFFFF:
                    d = self._pack('!BH', msg_encode_len, msg_encode, 126)
                else:
                    d = self._pack('!BQ', msg_encode_len, msg_encode, 127)
                self.wfile.write(d)
            except:
                self.wfile.flush()
                self.close_connection = True


class SimpleWSRequestHandler(BaseWSRequestHandler):
    def method(self):
        pass

def test(HandlerClass=SimpleWSRequestHandler, protocol="HTTP/1.1", port=8000, bind="127.0.0.1"):
    server_address = (bind, port)

    HandlerClass.protocol_version = protocol
    with ThreadingTCPServer(server_address, HandlerClass) as httpd:
        sa = httpd.socket.getsockname()
        serve_message = "Serving HTTP on {host} port {port} (http://{host}:{port}/) ..."
        print(serve_message.format(host=sa[0], port=sa[1]))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received, exiting.")
            sys.exit(0)

test()