import socket
import logging
from concurrent.futures import ThreadPoolExecutor
import sys
from routes.routes import routes
import os
from .utils import (
    get_allowed_headers,
    get_res_content_length,
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
MAX_THREADS = 10
TIMEOUT_VAL = 10
BYTES_RECV_AMT = 2048


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "[%(asctime)s] - %(levelname)s: %(message)s", datefmt="%d-%b-%Y %H:%M:%S"
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)


def start_server():
    host, port, directory = commandline_parser()
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
            sock.listen()
            logger.info(
                f"Server Listening on {host} port {port} (http://{host}:{port}/)"
            )

            while True:
                c_socket, c_address = sock.accept()
                # logger.info(f"Connected to {c_address}")
                executor.submit(handle_request, c_socket, c_address, directory)
        except KeyboardInterrupt:
            logger.info("Server terminated by user")
        except OSError as oe:
            logger.error(oe)
        # except Exception as e:
        #         print(f"Error: {e}")
        finally:
            logger.info("Connection Closed")
            sock.close()


def send_http_response(
    client_socket,
    client_address,
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
        alt_message = f"Connection has been Terminated with client {client_address}"
        if hasattr(pipe_error, "args") and pipe_error.args:
            alt_message += f"\nAdditional Details: {', '.join(str(args) for args in pipe_error.args)}"
        logger.warning(alt_message)


def handle_unsupported_request(client_socket):
    err_page = create_error_page(501)
    send_http_response(
        client_socket,
        err_page,
        501,
        get_status_texts(501),
        get_res_content_length(err_page),
        "text/html",
    )


def handle_request(client_socket: socket.socket, client_address, directory=None):
    buffer = b""
    client_socket.settimeout(TIMEOUT_VAL)
    try:
        body_buffer = None
        with client_socket:
            while True:
                data = client_socket.recv(BYTES_RECV_AMT)
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
                            body_data = client_socket.recv(BYTES_RECV_AMT)
                            if not body_data:
                                break
                            body_buffer += body_data
                            buffer += body_buffer
                    break

            # print(buffer)
            # print("body buffer: ", body_buffer)
            # parsed_header = parse_header(header_buffer)

            # parsed_body = parse_body(body_buffer)

            request_data = parse_request(buffer)
            if len(request_data) == 0:
                message = "Incorrect http request format"
                send_http_response(
                    client_socket,
                    client_address,
                    message,
                    400,
                    get_status_texts(400),
                    get_res_content_length(message),
                )
                logger.error(
                    f"{client_address[0]} 400 {get_status_texts(400)}, message: Incorrect http request format"
                )
            # print(request_data)

            if request_data["headers"].get("method") == "GET":
                handle_get_request(
                    client_socket,
                    client_address,
                    request_data.get("headers"),
                    directory,
                )
            elif request_data["headers"].get("method") == "HEAD":
                handle_head_request(
                    client_socket, client_address, request_data.get("headers")
                )
            else:
                logger.error(
                    f"{client_address[0]} - {request_data['headers'].get('method')} {request_data['headers'].get('path')} 501"
                )
                handle_unsupported_request(client_socket)

    except KeyError:
        logger.error("Failed to Parse request")

    except socket.timeout:
        logger.info(f"Connection Timeout for client {client_address[0]}")


def handle_get_request(client_socket, client_address, getreq_data, directory):
    # print(f"\nMetadata dictionary: {getreq_data.get('metadata')}\n")
    path = getreq_data.get("path")
    method = getreq_data.get("method")
    if directory:
        handle_directory_listing(client_socket, client_address, directory, path)
    else:
        allowed_headers = get_allowed_headers()
        accept_headers = getreq_data.get("metadata").get("accept")
        request_mime_type = get_mime_type(path)
        if any(header in accept_headers for header in allowed_headers):
            clean_path = os.path.normpath(
                os.path.join(ROOT_PATH, parse_path(path, encode=False).lstrip("/"))
            )
            if os.path.isfile(clean_path):
                # logger.info(
                #     f"{client_address} {method} {parse_path(path, encode=False)}"
                # )
                serve_file(
                    client_socket,
                    client_address,
                    parse_path(path, encode=False),
                    parse_path(path, encode=False),
                )
            else:
                if any(path in route for route in routes):
                    for route in routes:
                        if route.get(path, ""):
                            # logger.info(
                            #     f"{client_address} {method} {parse_path(path, encode=False)}"
                            # )
                            serve_file(
                                client_socket,
                                client_address,
                                route[path],
                                parse_path(path, encode=False),
                            )
                else:
                    logger.info(
                        f"{client_address[0]} - {method} {parse_path(path, encode=False)} 404"
                    )
                    serve_error_page(client_socket, client_address, 404)
        else:
            message = "415 Unsupported Media Type"
            send_http_response(
                client_socket,
                client_address,
                message,
                415,
                get_status_texts(415),
                get_res_content_length(message),
            )
            logger.error("415 Unsupported Media Type")


def handle_head_request(client_socket, client_address, req_headers):
    resource_path = req_headers.get("path")
    resource_method = req_headers.get("method")
    if any(resource_path in route for route in routes):
        for route in routes:
            if route.get(resource_path, ""):
                file_path = os.path.normpath(
                    os.path.join(ROOT_PATH, route[resource_path].lstrip("/"))
                )
                content_type = get_mime_type(file_path)
                content_length = get_res_content_length(file_path, is_path=True)
                response_header = f"HTTP/1.1 200 {get_status_texts(200)}\r\nContent-Length: {content_length}\r\nContent-Type: {content_type}\r\n\r\n"
                client_socket.sendall(response_header.encode("utf-8"))
                logger.info(
                    f"{client_address[0]} - {resource_method} {parse_path(resource_path, encode=False)}"
                )
    else:
        serve_error_page(client_socket, client_address, 404)
        logger.info(
            f"{client_address[0]} - {resource_method} {parse_path(resource_path, encode=False)} 404"
        )


def handle_directory_listing(client_socket, client_address, directory_path, url_path):
    stripped_urL_path = url_path.lstrip("/")
    combined_path = os.path.normpath(os.path.join(directory_path, stripped_urL_path))
    decoded_path = parse_path(combined_path, False)
    if os.path.isdir(combined_path):
        page = create_dirlist_page(combined_path, stripped_urL_path)
        if not page:
            logger.info(
                f"{client_address[0]} - GET {parse_path(url_path, encode=False)} 404"
            )
            serve_error_page(client_socket, client_address, 404)
        else:
            send_http_response(
                client_socket,
                client_address,
                page,
                200,
                get_status_texts(200),
                get_res_content_length(page),
                "text/html",
            )
            logger.info(
                f"{client_address[0]} - GET {parse_path(url_path, encode=False)} 200"
            )
    elif os.path.isfile(decoded_path):
        # logger.info(f"{client_address} - GET {parse_path(url_path, encode=False)}")
        serve_file(
            client_socket,
            client_address,
            decoded_path,
            parse_path(url_path, encode=False),
            True,
        )
    else:
        # message = "Directory or file not found"
        serve_error_page(client_socket, client_address, 404)
        logger.info(
            f"{client_address[0]} - GET {parse_path(url_path, encode=False)} 404"
        )


def serve_file(
    client_socket, client_address, file_path: str, request_line, directory_serve=False
):
    if not directory_serve:
        norm_path = os.path.normpath(os.path.join(ROOT_PATH, file_path.lstrip("/")))
        mime_type = get_mime_type(norm_path)
        if os.path.isfile(norm_path):
            try:
                with open(norm_path, "r") as f:
                    data = f.read()
                    send_http_response(
                        client_socket,
                        client_address,
                        data,
                        200,
                        get_status_texts(200),
                        get_res_content_length(data),
                        mime_type,
                    )
                    logger.info(
                        f"{client_address[0]} - GET {parse_path(request_line, encode=False)} 200"
                    )
            except FileNotFoundError:
                # print("File does not exist")
                logger.warning(
                    f"{client_address[0]} - GET {parse_path(norm_path, encode=False)} 404 {get_status_texts(404)}"
                )
                serve_error_page(client_socket, client_address, 404)
            except UnicodeDecodeError:
                logger.error(
                    f"{client_address[0]} - GET {parse_path(norm_path, encode=False)} 500 {get_status_texts(500)}"
                )
                logger.error(f"UnicodeDecodeError on file {norm_path}")
                serve_error_page(client_socket, client_address, 500)
            except UnicodeEncodeError:
                logger.error(
                    f"{client_address[0]} - GET {parse_path(norm_path, encode=False)} 500 {get_status_texts(500)}"
                )
                logger.error(f"UnicodeEncodeError on file {norm_path}")
                serve_error_page(client_socket, client_address, 500)
        else:
            # print("File does not exist")
            logger.info(
                f"{client_address[0]} - GET {parse_path(norm_path, encode=False)} 404 {get_status_texts(404)}"
            )
            serve_error_page(client_socket, client_address, 404)
    else:
        norm_path_d = os.path.normpath(file_path)
        mime_type = get_mime_type(norm_path_d)
        try:
            if is_binary_mime_type(mime_type):
                with open(norm_path_d, "rb") as f:
                    data = f.read()
                    send_http_response(
                        client_socket,
                        client_address,
                        data,
                        200,
                        get_status_texts(200),
                        get_res_content_length(data),
                        mime_type,
                    )
                    logger.info(
                        f"{client_address[0]} - GET {parse_path(request_line, encode=False)} 200"
                    )
            else:
                with open(norm_path_d, "r") as f:
                    data = f.read()
                    send_http_response(
                        client_socket,
                        client_address,
                        data,
                        200,
                        get_status_texts(200),
                        get_res_content_length(data),
                        mime_type,
                    )
                    logger.info(
                        f"{client_address[0]} - GET {parse_path(request_line, encode=False)} 200"
                    )
        except FileNotFoundError:
            # print("File does not exist")
            logger.warning(
                f"{client_address[0]} - GET {parse_path(norm_path_d, encode=False)} 404 {get_status_texts(404)}"
            )
            serve_error_page(client_socket, client_address, 404)
        except UnicodeDecodeError:
            logger.error(
                f"{client_address[0]} - GET {parse_path(norm_path_d, encode=False)} 500 {get_status_texts(500)}"
            )
            logger.error(f"UnicodeDecodeError on file {norm_path_d}")
            # print(f"UnicodeDecodeError on file {norm_path_d}")
            serve_error_page(client_socket, client_address, 500)


def serve_error_page(client_socket, client_address, error_code):
    err_page = create_error_page(error_code)
    send_http_response(
        client_socket,
        client_address,
        err_page,
        error_code,
        get_status_texts(error_code),
        get_res_content_length(err_page),
        "text/html",
    )


if __name__ == "__main__":
    start_server()
