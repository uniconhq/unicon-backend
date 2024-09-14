from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("unicon_backend/templates"), autoescape=select_autoescape()
)
template = env.get_template("run.jinja")
