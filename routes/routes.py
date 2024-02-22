from server.utils import route, route_list

routes = route_list(
    route("/", "index.html"),
    route("/about", "aboutme.html"),
    route("/ping", "pong.html"),
)
