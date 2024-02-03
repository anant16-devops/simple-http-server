import socket
import sys
from myutils import get_status_texts, parse_request


def start_server():
    host = "127.0.0.1"
    port = 8080
    if len(sys.argv) == 1:
        pass
    elif len(sys.argv[1:]) % 2 == 0:
        for i in range(1, len(sys.argv), 2):
            if sys.argv[i] == "-h":
                host = sys.argv[i + 1]
            elif sys.argv[i] == "-p":
                port = int(sys.argv[i + 1])
            else:
                print(f"Unsupported arguement: {sys.argv[i]}")
    else:
        print("Usage: python script.py [-h <host>] [-p <port>]")
        return

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, port))

        sock.listen()
        print(f"Listening on {host}:{port}")

        while True:
            c_socket, c_address = sock.accept()
            print(f"Connected to {c_address}")
            handle_request(c_socket)
    except KeyboardInterrupt:
        print("Server terminated by user")
    # except Exception as e:
    #         print(f"Error: {e}")
    finally:
        sock.close()


def send_http_response(
    client_socket, response_body, status_code, status_message, content_type="text/plain"
):
    response = f"HTTP/1.1 {status_code} {status_message}\r\nContent-Length: {len(response_body)}\r\nContent-Type:{content_type}\r\n\r\n{response_body}"
    client_socket.sendall(response.encode("utf-8"))


def handle_unsupported_request(client_socket):
    message = "Not Implemented"
    response_data = "Not Implemented: Unsupported HTTP method"
    send_http_response(client_socket, response_data, 501, get_status_texts(501))


def handle_request(client_socket):
    with client_socket:
        data = client_socket.recv(1024)
        try:
            # header, *_ = data.split("\r\n\r\n")
            request_data = parse_request(data)
            print(request_data)

            # response = header.split("\r\n")

            # print(response)

            # method, url, http_version = response[0].split(" ")
            # response_metadata = response[1:]
        except ValueError:
            print("Incorrect http request format")
            return

        if request_data.get("method") != "GET":
            handle_unsupported_request(client_socket)
        else:
            handle_get_request(
                client_socket, request_data.get("path"), request_data.get("metadata")
            )


def handle_get_request(client_socket, path, metadata):
    print(f"\nMetadata dictionary: {metadata}\n")
    if (path == "/" or path == "/ping") and (
        "*/*" in metadata.get("Accept")
        or "text/plain" in metadata.get("Accept")
        or "text/html" in metadata.get("Accept") 
    ):
        try:
            with open("./static/index.html", "r") as f:
                data = f.read()
                send_http_response(
                    client_socket, data, 200, get_status_texts(200), "text/html"
                )
        except FileNotFoundError:
            data = "Resource not found"
            send_http_response(client_socket, data, 404, get_status_texts(404))
    else:
        data = "Not Found"
        send_http_response(client_socket, data, 404, get_status_texts(404))


start_server()
