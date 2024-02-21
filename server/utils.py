import argparse
import re
import os
import urllib.parse


def get_status_texts(status_code):
    status_texts = {
        100: "Continue",
        101: "Switching Protocols",
        102: "Processing",
        103: "Early Hints",
        200: "OK",
        201: "Created",
        202: "Accepted",
        203: "Non-Authoritative Information",
        204: "No Content",
        205: "Reset Content",
        206: "Partial Content",
        207: "Multi-Status",
        208: "Already Reported",
        226: "IM Used",
        300: "Multiple Choices",
        301: "Moved Permanently",
        302: "Found",
        303: "See Other",
        304: "Not Modified",
        307: "Temporary Redirect",
        308: "Permanent Redirect",
        400: "Bad Request",
        401: "Unauthorized",
        402: "Payment Required",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        406: "Not Acceptable",
        407: "Proxy Authentication Required",
        408: "Request Timeout",
        409: "Conflict",
        410: "Gone",
        411: "Length Required",
        412: "Precondition Failed",
        413: "Content Too Large",
        414: "URI Too Long",
        415: "Unsupported Media Type",
        416: "Range Not Satisfiable",
        417: "Expectation Failed",
        418: "I'm a teapot",
        421: "Misdirected Request",
        422: "Unprocessable Content",
        423: "Locked",
        424: "Failed Dependency",
        425: "Too Early",
        426: "Upgrade Required",
        428: "Precondition Required",
        429: "Too Many Requests",
        431: "Request Header Fields Too Large",
        451: "Unavailable For Legal Reasons",
        500: "Internal Server Error",
        501: "Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
        505: "HTTP Version Not Supported",
        506: "Variant Also Negotiates",
        507: "Insufficient Storage",
        508: "Loop Detected",
        510: "Not Extended",
        511: "Network Authentication Required",
    }

    return status_texts[status_code]


def get_req_content_length(headers):
    has_cl = re.search(b"Content-Length: (\\d+)", headers, re.IGNORECASE)
    if has_cl:
        return int(has_cl.group(1))
    else:
        return None


def get_res_content_length(response, is_path=False):
    if is_path:
        try:
            mime_type = get_mime_type(response)
            is_binary = is_binary_mime_type(mime_type)
            if is_binary:
                with open(response, "rb") as f:
                    return len(f.read())
            else:
                with open(response, "r") as f:
                    return len(f.read())

        except FileNotFoundError:
            print("File not found")
    else:
        return len(response)


def create_dirlist_page(directory_path, url_path):
    directory_contents = []
    try:
        directory_contents = os.listdir(directory_path)
    except FileNotFoundError:
        print(f"{url_path} not found")
        return

    html_page = '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Directory Listing</title></head>'
    if url_path == "":
        html_page += f"<body><h1>Directory Listing for / </h1><hr>"
    else:
        html_page += f"<body><h1>Directory Listing for /{url_path}</h1><hr>"
    html_page += "<ul>"

    for content in directory_contents:
        encoded_content = parse_path(content)
        if os.path.isdir(f"{directory_path}/{content}/"):
            html_page += f'<li><a href="{encoded_content}/">{content}/</a></li>'
        else:
            html_page += f'<li><a href="{encoded_content}">{content}</a></li>'
    html_page += "</ul><hr></body></html>"

    return html_page


def create_error_page(error_code):
    error_status = f"{error_code} {get_status_texts(error_code)}"

    html_page = f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{error_status}</title></head>'
    html_page += '<body><div style="display: flex; justify-content: center; align-items: center; height: 90vh; width: 80vw; margin: auto;">'
    html_page += f'<h1 id="content" style="font-size: 2cm;">{error_status}</h1></div></body></html>'

    return html_page


def parse_body(request):
    pass


def parse_request(request):
    try:
        decoded_data: str = request.decode("utf-8")
    except UnicodeDecodeError:
        error = "Error Decoding response to utf-8"
        print(error)
        return {}

    decoded_data = decoded_data.replace("\r\n", "\n")
    try:
        header, *body = decoded_data.split("\n\n")
        request_line, *metadata = header.split("\n")
        method, path, http_version = request_line.split(" ")
        metadata = {i.split(": ")[0].lower(): i.split(": ")[1] for i in metadata}
    except ValueError:
        print("Incorrect http request format")
        return {}
    except IndexError:
        print("Incorrect http request format")
        return {}

    return {
        "headers": {
            "method": method,
            "path": path,
            "http_version": http_version,
            "metadata": metadata,
        },
        "body": body,
    }


def commandline_parser():
    parser = argparse.ArgumentParser(
        prog="Simple HTTP server", usage="script.py [-h <host>] [-p <port>]"
    )

    parser.add_argument(
        "-hs",
        "--host",
        dest="host",
        default="127.0.0.1",
        required=False,
        type=str,
        nargs="?",
    )
    parser.add_argument(
        "-p", "--port", dest="port", default="8000", required=False, type=int, nargs="?"
    )
    parser.add_argument(
        "-sd", "--sdir", dest="directory", required=False, type=str, nargs="?"
    )

    parsed_args = parser.parse_args()
    return (parsed_args.host, parsed_args.port, parsed_args.directory)


def get_mime_type(path_file_name):
    extension = path_file_name.split(".")[-1]
    mime_type_dict = {
        "html": "text/html",
        "css": "text/css",
        "js": "application/javascript",
        "json": "application/json",
        "pdf": "application/pdf",
        "xml": "text/xml",
        "png": "image/png",
        "py": "text/plain",
        "svg": "image/svg+xml",
        "svg+xml": "image/svg+xml",
        "c": "text/plain",
        "cpp": "text/plain",
        "csv": "text/csv",
        "webp": "image/webp",
        "txt": "text/plain",
    }

    return mime_type_dict.get(extension, "application/octet-stream")


def parse_path(path, encode=True):
    if encode:
        return urllib.parse.quote(path)
    else:
        return urllib.parse.unquote(path)


def is_binary_mime_type(mime_type):
    binary_mime_types = [
        "application/octet-stream",
        "image/jpeg",
        "image/png",
        "image/gif",
        "application/pdf",
        "application/zip",
    ]
    return mime_type in binary_mime_types


def get_allowed_headers():
    return [
        "text/css",
        "*/*",
        "text/html",
        "application/json",
        "application/javascript",
    ]


def route(path, file):
    return {path: file}


def route_list(*route):
    return list(route)
