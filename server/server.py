import socket
import logging
from routes import routes
import os
from .utils import (
    get_allowed_headers,
    get_status_texts,
    commandline_parser,
    get_mime_type,
    get_req_content_length,
    is_binary_mime_type,
    parse_request,
    create_dirlist_page,
    create_error_page,
    parse_path,
)

ROOT_PATH = "./static/"


def setup_logger():
    pass


def start_server():
    host, port, directory = commandline_parser()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.listen()
        print(f"Listening on {host}:{port}")

        while True:
            c_socket, c_address = sock.accept()
            print(f"Connected to {c_address}")
            handle_request(c_socket, directory)
    except KeyboardInterrupt:
        print("Server terminated by user")
    # except Exception as e:
    #         print(f"Error: {e}")
    finally:
        sock.close()


def send_http_response(
    client_socket,
    response_body,
    status_code,
    status_message,
    content_len,
    content_type="text/plain",
    encoding="utf-8",
):
    try:
        if is_binary_mime_type(content_type):
            response_header = f"HTTP/1.1 {status_code} {status_message}\r\nContent-Length: {content_len}\r\nContent-Type: {content_type}\r\n\r\n"
            client_socket.sendall(response_header.encode(encoding))
            client_socket.sendall(response_body)
        else:
            response = f"HTTP/1.1 {status_code} {status_message}\r\nContent-Length: {content_len}\r\nContent-Type: {content_type}\r\n\r\n{response_body}"
            client_socket.sendall(response.encode(encoding))

    except BrokenPipeError as pipe_error:
        alt_message = "Connection has been Terminated"
        if hasattr(pipe_error, "args") and pipe_error.args:
            alt_message += f"\nAdditional Details: {', '.join(str(args) for args in pipe_error.args)}"
        print(alt_message)


def handle_unsupported_request(client_socket):
    err_page = create_error_page(501)
    send_http_response(client_socket, err_page, 501, get_status_texts(501), len(err_page), "text/html")


def handle_request(client_socket: socket.socket, directory=None):
    buffer = b""
    client_socket.settimeout(10)
    try:
        body_buffer = None
        with client_socket:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break
                buffer += data

                if b"\r\n\r\n" in buffer:
                    header_index = buffer.find(b"\r\n\r\n") + len(b"\r\n\r\n")
                    header_buffer = buffer[:header_index]
                    body_buffer = buffer[header_index:]

                    has_contentlength = get_req_content_length(header_buffer)
                    if has_contentlength:
                        while len(body_buffer) < has_contentlength:
                            body_data = client_socket.recv(1024)
                            if not body_data:
                                break
                            body_buffer += body_data
                            buffer += body_buffer
                    break

            print(buffer)
            print("body buffer: ", body_buffer)
            # parsed_header = parse_header(header_buffer)

            # parsed_body = parse_body(body_buffer)

            request_data = parse_request(buffer)
            if len(request_data) == 0:
                message = "Incorrect http request format"
                send_http_response(
                    client_socket,
                    message,
                    400,
                    get_status_texts(400),
                    len(message)
                )
            print(request_data)

            if request_data["headers"].get("method") == "GET":
                handle_get_request(
                    client_socket, request_data.get("headers"), directory
                )
            elif request_data["headers"].get("method") == "HEAD":
                handle_head_request(client_socket, request_data.get("headers"))
            else:
                handle_unsupported_request(client_socket)

    except KeyError:
        print("Failed to Parse request")

    except socket.timeout:
        print("Connection Timeout")


def handle_get_request(client_socket, getreq_data, directory):
    print(f"\nMetadata dictionary: {getreq_data.get('metadata')}\n")
    path = getreq_data.get("path")
    if directory:
        handle_directory_listing(client_socket, directory, path)
    else:
        allowed_headers = get_allowed_headers()
        accept_headers = getreq_data.get("metadata").get("accept")
        request_mime_type = get_mime_type(path)
        if any(header in accept_headers for header in allowed_headers):
            if any(path in route for route in routes):
                for route in routes:
                    if route.get(path, ""):
                        serve_file(client_socket, route[path])
            else:
                serve_error_page(client_socket, 404)
        else:
            message = "415 Unsupported Media Type"
            send_http_response(
                client_socket, message, 415, get_status_texts(415), len(message)
            )


def handle_head_request(client_socket, req_headers):
    resource_path = req_headers.get("path")
    if any(resource_path in route for route in routes):
        for route in routes:
            if route.get(resource_path, ""):
                file_path = os.path.normpath(os.path.join(ROOT_PATH, route[resource_path].lstrip("/")))
                content_type = get_mime_type(file_path)
                response_header = f"HTTP/1.1 200 {get_status_texts(200)}\r\nContent-Length: {os.path.getsize(file_path)}\r\nContent-Type: {content_type}\r\n\r\n"
                client_socket.sendall(response_header.encode('utf-8'))
    else:
        serve_error_page(client_socket, 404)


def handle_directory_listing(client_socket, directory_path, url_path):
    stripped_urL_path = url_path.lstrip("/")
    combined_path = os.path.normpath(os.path.join(directory_path, stripped_urL_path))
    decoded_path = parse_path(combined_path, False)
    if os.path.isdir(combined_path):
        page = create_dirlist_page(combined_path, stripped_urL_path)
        if not page:
            serve_error_page(client_socket, 404)
        else:
            send_http_response(
                client_socket, page, 200, get_status_texts(200), len(page), "text/html"
            )
    elif os.path.isfile(decoded_path):
        serve_file(client_socket, decoded_path, True)
    else:
        message = "Directory or file not found"
        serve_error_page(client_socket, 404)
        print(message)


def serve_file(client_socket, file_path: str, directory_serve=False):
    if not directory_serve:
        norm_path = os.path.normpath(os.path.join(ROOT_PATH, file_path.lstrip("/")))
        mime_type = get_mime_type(norm_path)
        if os.path.isfile(norm_path):
            try:
                with open(norm_path, "r") as f:
                    data = f.read()
                    send_http_response(
                        client_socket, data, 200, get_status_texts(200), os.path.getsize(norm_path), mime_type
                    )
            except FileNotFoundError:
                print("File does not exist")
                serve_error_page(client_socket, 404)
            except UnicodeDecodeError:
                print(f"UnicodeDecodeError on file {norm_path}")
                serve_error_page(client_socket, 500)
            except UnicodeEncodeError:
                print(f"UnicodeEncodeError on file {norm_path}")
                serve_error_page(client_socket, 500)
        else:
            print("File does not exist")
            serve_error_page(client_socket, 404)
    else:
        norm_path_d = os.path.normpath(file_path)
        mime_type = get_mime_type(norm_path_d)
        try:
            if is_binary_mime_type(mime_type):
                with open(norm_path_d, "rb") as f:
                    data = f.read()
                    send_http_response(
                        client_socket, data, 200, get_status_texts(200), os.path.getsize(norm_path_d), mime_type
                    )
            else:
                with open(norm_path_d, "r") as f:
                    data = f.read()
                    send_http_response(
                        client_socket, data, 200, get_status_texts(200), os.path.getsize(norm_path_d), mime_type
                    )
        except FileNotFoundError:
            print("File does not exist")
            serve_error_page(client_socket, 404)
        except UnicodeDecodeError:
            print(f"UnicodeDecodeError on file {norm_path_d}")
            serve_error_page(client_socket, 500)


def serve_error_page(client_socket, error_code):
    err_page = create_error_page(error_code)
    send_http_response(
        client_socket, err_page, error_code, get_status_texts(error_code), len(err_page), "text/html"
    )


if __name__ == "__main__":
    start_server()
